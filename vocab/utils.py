import requests
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

# ==============================================================================
# [1] 기존 로직 유지 (오답 추출 등)
# ==============================================================================
def get_vulnerable_words(profile):
    """
    오답률 높은 단어 + 학생이 직접 추가한 오답 단어 병합
    """
    normal_details = TestResultDetail.objects.filter(result__student=profile)
    monthly_details = MonthlyTestResultDetail.objects.filter(result__student=profile)

    stats = {}
    def update_stats(queryset):
        for d in queryset:
            key = d.word_question.strip().lower()
            if key not in stats: stats[key] = {'total': 0, 'wrong': 0}
            stats[key]['total'] += 1
            if not d.is_correct: stats[key]['wrong'] += 1

    update_stats(normal_details)
    update_stats(monthly_details)

    vulnerable_keys = {text for text, data in stats.items() if data['total'] > 0 and (data['wrong'] / data['total'] >= 0.25)}

    personal_wrongs = PersonalWrongWord.objects.filter(student=profile).select_related('word')
    for pw in personal_wrongs:
        vulnerable_keys.add(pw.word.english.strip().lower())
    
    if not vulnerable_keys:
        return []

    candidates = Word.objects.filter(english__in=vulnerable_keys).select_related('book')

    recent_tests = TestResult.objects.filter(student=profile).order_by('-created_at').values_list('book_id', flat=True)[:20]
    recent_book_ids = list(dict.fromkeys(recent_tests))

    def get_priority(word):
        if word.book_id in recent_book_ids:
            return recent_book_ids.index(word.book_id)
        return 9999

    sorted_candidates = sorted(candidates, key=get_priority)

    unique_words = []
    seen_english = set()

    for w in sorted_candidates:
        clean_eng = w.english.strip().lower()
        if clean_eng not in seen_english:
            unique_words.append(w)
            seen_english.add(clean_eng)
    
    return unique_words

def is_monthly_test_period():
    import calendar
    now = timezone.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day > (last_day - 8)

# ==============================================================================
# [2] 외부 사전 검색 (네이버 자동완성 API 활용)
# ==============================================================================
def crawl_daum_dic(query):
    """
    [최종 해결] 네이버 영어사전 자동완성 API 활용
    - HTML 파싱 X -> 데이터(JSON) 직접 수신 (속도 빠름, 차단 없음)
    - 주소: ac.dict.naver.com (매우 안정적)
    """
    print(f"--- [DEBUG] 네이버 자동완성 API 요청: {query} ---")
    try:
        # 네이버 영어사전 자동완성 API URL
        url = "https://ac.dict.naver.com/en/ac"
        
        params = {
            'st': '11001',   # 검색 대상 (영어사전)
            'r_lt': '11001', # 결과 타입
            'q': query,      # 검색어
            'q_enc': 'utf-8',
            'r_format': 'json'
        }
        
        # 일반 브라우저처럼 보이게 헤더 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://en.dict.naver.com/'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=3)
        
        if response.status_code != 200:
            print(f"--- [DEBUG] API 상태 코드 오류: {response.status_code} ---")
            return None
            
        # JSON 데이터 파싱
        data = response.json()
        
        # 데이터 구조: { "items": [ [ ["word", "html_word", "meaning", ...], ... ] ] }
        items_group = data.get('items', [])
        
        if not items_group or not items_group[0]:
            print("--- [DEBUG] API 검색 결과 없음 ---")
            return None
            
        # 결과 목록 (첫 번째 그룹)
        results = items_group[0]
        
        # 1. 검색어와 정확히 일치하는 단어 찾기
        target_item = None
        for item in results:
            # item[0] = 단어 (예: "apple"), item[2] = 뜻 (예: "1. 사과 2. ...")
            if item[0].lower() == query.lower():
                target_item = item
                break
        
        # 2. 없으면 첫 번째 결과 사용
        if not target_item:
            target_item = results[0]
            
        english = target_item[0]
        korean = target_item[2] # 뜻 부분
        
        # 뜻 정제 (HTML 태그가 포함될 수 있어 제거하거나 그대로 사용)
        # 네이버 API는 뜻에 '1. 사과' 처럼 깔끔하게 주는 편입니다.
        
        print(f"--- [DEBUG] API 성공: {english} -> {korean} ---")
        
        return {
            'english': english,
            'korean': korean,
            'source': 'naver_api'
        }
        
    except Exception as e:
        print(f"--- [DEBUG] API 예외 발생: {e} ---")
        return None