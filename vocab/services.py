# vocab/services.py
from django.utils import timezone
# [수정] StudentProfile import 불필요 (인자로 받을 것이므로)

def calculate_score(details_data):
    """
    서버 사이드 채점 로직 (개선됨)
    1. 띄어쓰기 무시
    2. 콤마(,)로 구분된 정답 중 하나라도 맞으면 정답 인정
    3. [NEW] 학생이 콤마로 여러 뜻을 적었을 경우, 그 중 하나라도 맞으면 정답 인정
    4. [NEW] NFC 정규화로 맥/윈도우 한글 호환성 해결
    """
    score = 0
    wrong_count = 0
    processed_details = []

    for item in details_data:
        # 1. 입력값 가져오기 (없으면 빈 문자열)
        user_input = item.get('user_input', '')
        ans_origin = item.get('korean', '')

        # 2. NFC 정규화 (맥북/아이폰 등에서 자모 분리되는 현상 방지)
        user_norm = unicodedata.normalize('NFC', user_input)
        ans_norm = unicodedata.normalize('NFC', ans_origin)

        # 3. 학생 답안 전처리: 콤마로 쪼개고, 공백 제거 & 소문자 변환
        # 예: "사과, 애플" -> ['사과', '애플']
        user_tokens = [
            u.replace(" ", "").strip().lower() 
            for u in user_norm.split(',') if u.strip()
        ]
        
        # 4. 정답지 전처리: 콤마로 쪼개기
        ans_candidates = [
            a.replace(" ", "").strip().lower() 
            for a in ans_norm.split(',')
        ]
        
        # 5. 채점 로직 개선:
        # 학생이 쓴 답안 덩어리 중 하나라도 정답 후보군에 포함되어 있으면 정답 처리
        is_correct = False
        
        if not user_tokens: # 답을 안 쓴 경우
            is_correct = False
        else:
            for token in user_tokens:
                if token in ans_candidates:
                    is_correct = True
                    break
        
        if is_correct:
            score += 1
        else:
            wrong_count += 1
            
        processed_details.append({
            'q': item.get('english'),
            'u': user_input,      # 원본 입력값 저장
            'a': ans_origin,      # 원본 정답 저장
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