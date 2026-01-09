import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

def get_vulnerable_words(profile):
    """
    [수정] 오답률 높은 단어 + 학생이 직접 추가한 오답 단어 병합
    """
    # 1. 기존 오답 데이터 수집
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

    # 2. 학생 추가 오답
    personal_wrongs = PersonalWrongWord.objects.filter(student=profile).select_related('word')
    for pw in personal_wrongs:
        clean_word = pw.word.english.strip().lower()
        vulnerable_keys.add(clean_word)
    
    if not vulnerable_keys:
        return []

    # 3. DB 조회
    candidates = Word.objects.filter(english__in=vulnerable_keys).select_related('book')

    # 4. 정렬
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
    now = timezone.now()
    import calendar
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day > (last_day - 8)

def crawl_daum_dic(query):
    """
    [변경] Daum 서버 차단 이슈로 인해 Naver 사전으로 타겟 변경
    (views.py 와의 호환성을 위해 함수 이름은 유지)
    """
    print(f"--- [DEBUG] 네이버 사전 크롤링 시작: {query} ---")
    try:
        # 네이버 통합 사전 검색 URL
        url = f"https://dict.naver.com/search.dict?dicQuery={query}&query={query}&target=dic&ie=utf8&query_utf=&isOnlyViewEE="
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"--- [DEBUG] 응답 오류: {response.status_code} ---")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 검색 결과 영역 찾기 (.dic_search_result)
        result_container = soup.select_one('.dic_search_result')
        
        if not result_container:
            print("--- [DEBUG] 검색 결과 영역(.dic_search_result) 없음. 검색어 확인 필요 ---")
            # 검색 결과가 아예 없는 경우 HTML 구조가 다를 수 있음
            return None

        # 2. 단어 추출 (dt > strong 또는 dt > a > strong)
        dt = result_container.select_one('dt')
        if not dt:
            print("--- [DEBUG] 단어(dt) 영역 없음 ---")
            return None
            
        word_element = dt.select_one('strong')
        if word_element:
            english = word_element.text.strip()
        else:
            # 링크 안에 텍스트가 있는 경우 대비
            link = dt.select_one('a')
            english = link.text.strip() if link else dt.text.strip()

        # 3. 뜻 추출 (dd > ul > li)
        dd = result_container.select_one('dd')
        if not dd:
            print("--- [DEBUG] 뜻(dd) 영역 없음 ---")
            return None
            
        meanings = dd.select('ul > li')
        if meanings:
            # 여러 뜻이 리스트로 있는 경우 상위 3개 가져오기
            # (span 등의 태그 제거하고 순수 텍스트만)
            korean_list = []
            for m in meanings[:3]:
                # '1. ', '2. ' 같은 불필요한 숫자 제거 로직이 필요하면 추가 가능
                # 여기서는 텍스트 전체를 가져옴 (ex: "1. 사과")
                korean_list.append(m.text.strip())
            korean = ", ".join(korean_list)
        else:
            # 리스트 구조가 아닌 경우 (텍스트 통으로 가져오기)
            korean = dd.text.strip().split('\n')[0]

        print(f"--- [DEBUG] 크롤링 성공: {english} -> {korean} ---")
        
        return {
            'english': english,
            'korean': korean,
            'source': 'naver'
        }
        
    except Exception as e:
        print(f"--- [DEBUG] 크롤링 예외 발생: {e} ---")
        return None