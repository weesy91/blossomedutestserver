import requests
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

# ==============================================================================
# [1] 기존 로직: 오답 단어 추출 (이 부분이 없으면 에러가 납니다!)
# ==============================================================================
def get_vulnerable_words(profile):
    """
    오답률 높은 단어 + 학생이 직접 추가한 오답 단어 병합하여 반환
    """
    # 1. 기존 시험 오답 데이터 수집
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

    # 틀린 비율이 25% 이상인 단어 필터링
    vulnerable_keys = {text for text, data in stats.items() if data['total'] > 0 and (data['wrong'] / data['total'] >= 0.25)}

    # 2. 학생이 직접 추가한 오답 단어 수집
    personal_wrongs = PersonalWrongWord.objects.filter(student=profile).select_related('word')
    for pw in personal_wrongs:
        vulnerable_keys.add(pw.word.english.strip().lower())
    
    if not vulnerable_keys:
        return []

    # 3. 실제 Word 객체 조회
    candidates = Word.objects.filter(english__in=vulnerable_keys).select_related('book')

    # 4. 정렬 (최근 본 단어장 우선)
    recent_tests = TestResult.objects.filter(student=profile).order_by('-created_at').values_list('book_id', flat=True)[:20]
    recent_book_ids = list(dict.fromkeys(recent_tests))

    def get_priority(word):
        if word.book_id in recent_book_ids:
            return recent_book_ids.index(word.book_id)
        return 9999

    sorted_candidates = sorted(candidates, key=get_priority)

    # 5. 중복 제거
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
# [2] 외부 사전 검색 (구글 번역 API - 다의어 지원 버전)
# ==============================================================================
def crawl_daum_dic(query):
    """
    [업그레이드] 구글 번역 API (다의어 지원)
    - dt=['t', 'bd'] 파라미터를 통해 기본 번역 + 사전 정보(여러 뜻)를 함께 요청합니다.
    """
    print(f"--- [DEBUG] 구글 번역 API 요청(다의어): {query} ---")
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        
        # t: 문장 번역(Translation), bd: 사전 정보(Back Dictionary)
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "ko",
            "dt": ["t", "bd"], 
            "q": query
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code != 200:
            print(f"--- [DEBUG] 응답 오류: {response.status_code} ---")
            return None
        
        data = response.json()
        
        english = query
        korean_candidates = []
        
        # 1. 사전 데이터(data[1])가 있으면 거기서 여러 뜻을 가져옵니다.
        if len(data) > 1 and data[1]:
            for part_of_speech in data[1]:
                meanings = part_of_speech[1]
                # 각 품사별로 상위 3개 뜻만
                for m in meanings[:3]:
                    if m not in korean_candidates:
                        korean_candidates.append(m)
            
            # 리스트를 콤마로 연결 (최대 5~6개 정도만 표시 추천)
            korean = ", ".join(korean_candidates[:6])
            
        # 2. 사전 데이터가 없으면 기본 번역(data[0])을 사용
        else:
            if data and data[0] and data[0][0]:
                korean = data[0][0][0]
            else:
                return None

        print(f"--- [DEBUG] 번역 성공(다의어): {english} -> {korean} ---")
        
        return {
            'english': english,
            'korean': korean,
            'source': 'google_translate'
        }
        
    except Exception as e:
        print(f"--- [DEBUG] 예외 발생: {e} ---")
        return None