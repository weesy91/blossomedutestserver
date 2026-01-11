# vocab/services.py
from django.utils import timezone
import unicodedata
import re
# [수정] StudentProfile import 불필요 (인자로 받을 것이므로)


def clean_text(text):
    """
    텍스트 정제 함수
    1. 괄호와 그 안의 내용 제거: (매우)사려깊은 -> 사려깊은
    2. [핵심 수정] 숫자와 점(1. 2.)을 콤마(,)로 치환! -> 1. A 2. B -> A, B
    3. 특수문자 제거 (콤마 제외)
    """
    if not text: return ""
    
    # 1. 괄호와 그 안의 내용 제거 (소괄호, 대괄호)
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    
    # 2. [핵심] 숫자 목록(1. 2. 등)을 콤마로 변경하여 분리되게 함
    # 예: "1. 회피하다 2. 외면하다" -> ", 회피하다 , 외면하다"
    text = re.sub(r'\d+\.', ',', text)
    
    # 3. 특수문자 제거 (한글, 영문, 숫자, 콤마, 공백 제외하고 모두 제거)
    text = re.sub(r'[^\w\s,]', ' ', text)
    
    return text.strip()


def calculate_score(details_data):
    """
    서버 사이드 채점 로직
    - 정답지는 콤마(,)로 구분
    - 비교 시에는 모든 공백을 제거하여 '상호 작용하다' == '상호작용하다' 인정
    """
    score = 0
    wrong_count = 0
    processed_details = []

    for item in details_data:
        user_input = item.get('user_input', '')
        ans_origin = item.get('korean', '')
        
        if not user_input: user_input = ""
        if not ans_origin: ans_origin = ""

        # 1. NFC 정규화 (맥/윈도우 호환성)
        user_norm = unicodedata.normalize('NFC', user_input)
        ans_norm = unicodedata.normalize('NFC', ans_origin)

        # 2. 정답지 전처리 (숫자를 콤마로 변환)
        # "1. 회피하다 2. 외면하다" -> ", 회피하다 , 외면하다"
        cleaned_ans = clean_text(ans_norm)
        
        # 3. 정답 후보군 생성 (콤마로 분리)
        # -> ['', '회피하다', '', '외면하다'] -> ['회피하다', '외면하다']
        ans_candidates = [
            token.strip().lower() 
            for token in cleaned_ans.split(',') 
            if token.strip()
        ]

        # 4. 학생 답안 전처리 (콤마로 분리)
        user_tokens = [
            u.strip().lower() 
            for u in user_norm.split(',') 
            if u.strip()
        ]
        
        # 5. 채점 (공백 무시 비교)
        is_correct = False
        if not user_tokens:
            is_correct = False
        else:
            for u_token in user_tokens:
                # 학생 답: "상호작용하다" -> "상호작용하다"
                u_compact = u_token.replace(" ", "")
                # (혹시 모를 특수문자 제거)
                u_compact = clean_text(u_compact).replace(" ", "")

                for a_token in ans_candidates:
                    # 정답지: "상호 작용하다" -> "상호작용하다"
                    a_compact = a_token.replace(" ", "")
                    
                    if u_compact == a_compact:
                        is_correct = True
                        break
                if is_correct: break
        
        if is_correct:
            score += 1
        else:
            wrong_count += 1
            
        processed_details.append({
            'q': item.get('english'),
            'u': user_input,
            'a': ans_origin,
            'c': is_correct
        })
        
    return score, wrong_count, processed_details

def update_cooldown(profile, mode, score, test_range=None):
    """
    점수에 따라 쿨타임(재시험 대기시간) 설정
    [수정] user 대신 profile 객체를 직접 받습니다.
    """
    PASS_SCORE = 27
    
    # 1. 도전 모드
    if mode == 'challenge':
        if score >= PASS_SCORE: 
            profile.last_failed_at = None
        else: 
            profile.last_failed_at = timezone.now()
            
    # 2. 오답 모드 (또는 오답집중 범위)
    elif mode == 'wrong' or test_range == '오답집중':
        if score >= PASS_SCORE: 
            profile.last_wrong_failed_at = None
        else: 
            profile.last_wrong_failed_at = timezone.now()
            
    profile.save()