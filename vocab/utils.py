import requests
from django.utils import timezone
# (기존 import 유지)
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

# ... (get_vulnerable_words, is_monthly_test_period 함수는 기존 그대로 유지) ...

def crawl_daum_dic(query):
    """
    [업그레이드] 구글 번역 API (다의어 지원)
    - dt=['t', 'bd'] 파라미터를 통해 기본 번역 + 사전 정보(여러 뜻)를 함께 요청합니다.
    """
    print(f"--- [DEBUG] 구글 번역 API 요청(다의어): {query} ---")
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        
        # dt 파라미터를 리스트로 전달하면 requests가 알아서 dt=t&dt=bd 형태로 만들어줍니다.
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
        
        # data 구조:
        # data[0]: [ ["기본 번역", "영어원문", ...], ... ]
        # data[1]: [ ["품사", ["뜻1", "뜻2", ...], ...], ... ]  <- 여기가 사전 데이터!
        
        english = query
        korean_candidates = []
        
        # 1. 사전 데이터(data[1])가 있으면 거기서 여러 뜻을 가져옵니다.
        if len(data) > 1 and data[1]:
            for part_of_speech in data[1]:
                # part_of_speech[0]: 품사 (예: noun, verb)
                # part_of_speech[1]: 뜻 리스트 (예: ["사과", "사과나무"])
                meanings = part_of_speech[1]
                
                # 각 품사별로 상위 3개 뜻만 가져오기 (너무 많으면 지저분하므로)
                for m in meanings[:3]:
                    if m not in korean_candidates:
                        korean_candidates.append(m)
            
            # 리스트를 콤마로 연결 (최대 5~6개 정도만 표시 추천)
            korean = ", ".join(korean_candidates[:6])
            
        # 2. 사전 데이터가 없으면(예: 고유명사나 문장), 기본 번역(data[0])을 사용
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