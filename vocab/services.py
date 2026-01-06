# vocab/services.py
from django.utils import timezone
# [수정] StudentProfile import 불필요 (인자로 받을 것이므로)

def calculate_score(details_data):
    """
    서버 사이드 채점 로직 (띄어쓰기 무시)
    """
    score = 0
    wrong_count = 0
    processed_details = []

    for item in details_data:
        user_clean = item.get('user_input', '').replace(" ", "").strip()
        ans_clean = item.get('korean', '').replace(" ", "").strip()
        
        is_correct = (user_clean == ans_clean)
        
        if is_correct:
            score += 1
        else:
            wrong_count += 1
            
        processed_details.append({
            'q': item.get('english'),
            'u': item.get('user_input'),
            'a': item.get('korean'),
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