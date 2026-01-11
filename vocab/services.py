# vocab/services.py
from django.utils import timezone
import unicodedata
import re
# [수정] StudentProfile import 불필요 (인자로 받을 것이므로)


def clean_text(text):
    """
    텍스트 정제 함수
    1. 괄호와 그 안의 내용 제거: (매우)사려깊은 -> 사려깊은, [아주]적절한 -> 적절한
    2. 숫자와 점 제거: 1. 결합하다 -> 결합하다
    3. 특수문자 제거: ~, -, 등 제거
    4. 다중 공백을 단일 공백으로 축소
    """
    # 1. 괄호와 그 안의 내용 제거 (소괄호, 대괄호)
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    
    # 2. 숫자와 점 제거 (예: "1.", "2." 등)
    text = re.sub(r'\d+\.', '', text)
    
    # 3. 특수문자 제거 (한글, 영문, 숫자, 콤마 제외하고 모두 공백으로 변경)
    # 단, 콤마(,)는 구분자로 써야 하므로 살려둡니다.
    text = re.sub(r'[^\w\s,]', ' ', text)
    
    return text.strip()


def calculate_score(details_data):
    """
    서버 사이드 채점 로직 (최종 업그레이드 버전)
    - 콤마(,) 구분 지원
    - 숫자(1. 2.), 괄호(( ), [ ]), 특수문자 완벽 처리
    - 자모 분리(NFC) 해결
    """
    score = 0
    wrong_count = 0
    processed_details = []

    for item in details_data:
        user_input = item.get('user_input', '')
        ans_origin = item.get('korean', '')

        # 1. NFC 정규화 (맥/윈도우 호환성)
        user_norm = unicodedata.normalize('NFC', user_input)
        ans_norm = unicodedata.normalize('NFC', ans_origin)

        # 2. 정답지 전처리 (핵심 기능)
        # 예: "1. 결합하다 2. 묶이다" -> "결합하다  묶이다"
        # 예: "(매우) 사려깊은" -> " 사려깊은"
        cleaned_ans = clean_text(ans_norm)
        
        # 3. 정답 후보군 생성 (콤마 또는 공백으로 쪼개기)
        # "결합하다  묶이다" -> ['결합하다', '묶이다']
        # "적절한, 알맞은" -> ['적절한', '알맞은']
        ans_candidates = [
            token.strip().lower() 
            for token in re.split(r'[,\s]+', cleaned_ans) 
            if token.strip()
        ]

        # 4. 학생 답안 전처리 (콤마로만 구분)
        user_tokens = [
            u.strip().lower() 
            for u in user_norm.split(',') 
            if u.strip()
        ]
        
        # 5. 채점: 학생이 쓴 단어 중 하나라도 정답 후보군에 있으면 정답
        is_correct = False
        if not user_tokens:
            is_correct = False
        else:
            for u_token in user_tokens:
                # 괄호 같은 거 제거하고 순수 단어만 비교
                clean_u = clean_text(u_token).replace(" ", "") 
                
                for a_token in ans_candidates:
                    if clean_u == a_token:
                        is_correct = True
                        break
                if is_correct:
                    break
        
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