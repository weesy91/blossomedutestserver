import requests
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

# [기존 함수 유지]
def get_vulnerable_words(profile):
    """
    [수정] 오답률 높은 단어 + 학생이 직접 추가한 오답 단어 병합
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

# [기존 함수 유지]
def is_monthly_test_period():
    import calendar
    now = timezone.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day > (last_day - 8)

# [완전 교체]
def crawl_daum_dic(query):
    """
    [해결책] Daum 사전 자동완성 API (JSON) 활용
    - HTML 파싱이 아니므로 구조 변경/차단에 매우 강함
    """
    print(f"--- [DEBUG] Daum 자동완성 API 요청: {query} ---")
    try:
        # Daum 사전 API URL (cate=eng: 영어사전)
        url = "https://suggest-dic.daum.net/dic_all_v2.do"
        params = {
            'cate': 'eng', 
            'q': query
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=3)
        
        if response.status_code != 200:
            print(f"--- [DEBUG] API 상태 코드 오류: {response.status_code} ---")
            return None
            
        # JSON 데이터 파싱
        data = response.json()
        items = data.get('result', {}).get('items', [])
        
        if not items:
            print("--- [DEBUG] API 검색 결과 없음 ---")
            return None
            
        # 1. 검색어와 정확히 일치하는 단어 우선 탐색
        target_item = None
        for item in items:
            # item['keyword'] 예: "apple", "apple pie"
            if item['keyword'].lower() == query.lower():
                target_item = item
                break
        
        # 2. 일치하는 게 없으면 가장 첫 번째 결과 사용
        if not target_item:
            target_item = items[0]
            
        english = target_item['keyword']
        korean = target_item['mean'] # 예: "사과, 애플"
        
        print(f"--- [DEBUG] API 성공: {english} -> {korean} ---")
        
        return {
            'english': english,
            'korean': korean,
            'source': 'daum_api'
        }
        
    except Exception as e:
        print(f"--- [DEBUG] API 예외 발생: {e} ---")
        return None