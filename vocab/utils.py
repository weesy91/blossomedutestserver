import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

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

def is_monthly_test_period():
    import calendar
    now = timezone.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day > (last_day - 8)

def crawl_daum_dic(query):
    """
    [최종 수정] 네이버 영어사전(en.dict.naver.com) 크롤링
    전략 1: Meta Description (요약 정보) 활용 (구조 변화에 강함)
    전략 2: HTML 리스트 파싱 (보조)
    """
    print(f"--- [DEBUG] 네이버 영어사전 크롤링 시작: {query} ---")
    try:
        # 네이버 영어사전 전용 URL (더 정확한 결과)
        url = f"https://en.dict.naver.com/search.dict?query={query}"
        
        # 일반적인 브라우저 헤더
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"--- [DEBUG] 응답 오류: {response.status_code} ---")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [DEBUG] 페이지 제목 확인 (차단 여부 확인용)
        page_title = soup.title.text.strip() if soup.title else "No Title"
        print(f"--- [DEBUG] 페이지 제목: {page_title} ---")

        english = query
        korean = None

        # -----------------------------------------------------------
        # [전략 1] 메타 태그(Meta Description) 활용 (가장 강력함)
        # -----------------------------------------------------------
        # 예: <meta property="og:description" content="1. 사과 2. ...">
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            desc_content = meta_desc.get('content', '').strip()
            # 내용이 있고, 검색 결과 페이지가 아닌 구체적인 뜻일 경우 사용
            if desc_content and "영어사전" not in desc_content and "검색결과" not in desc_content:
                print(f"--- [DEBUG] Meta Tag에서 뜻 발견: {desc_content} ---")
                korean = desc_content
                # "apple : 1. 사과" 형식일 경우 앞부분 제거
                if ":" in korean:
                    parts = korean.split(":", 1)
                    if len(parts) > 1:
                        korean = parts[1].strip()

        # -----------------------------------------------------------
        # [전략 2] HTML 구조 파싱 (en.dict.naver.com 구조)
        # -----------------------------------------------------------
        if not korean:
            # 단어 목록 컨테이너 (row_col1)
            search_item = soup.select_one('.row_col1')
            if search_item:
                # 단어 텍스트 확인
                word_elem = search_item.select_one('strong') or search_item.select_one('a.link')
                if word_elem:
                    english = word_elem.text.strip()
                
                # 뜻 확인 (p.mean > span)
                mean_elems = search_item.select('p.mean span')
                if not mean_elems:
                    # 다른 구조 시도 (list_mean)
                    mean_elems = search_item.select('.list_mean li')
                
                if mean_elems:
                    korean_list = [m.text.strip() for m in mean_elems[:3]]
                    korean = ", ".join(korean_list)

        if not korean:
            print(f"--- [DEBUG] 뜻을 찾을 수 없음. HTML 일부: {soup.text[:200]} ---")
            return None
            
        print(f"--- [DEBUG] 크롤링 성공: {english} -> {korean} ---")
        
        return {
            'english': english,
            'korean': korean,
            'source': 'naver_en'
        }
        
    except Exception as e:
        print(f"--- [DEBUG] 크롤링 예외 발생: {e} ---")
        return None