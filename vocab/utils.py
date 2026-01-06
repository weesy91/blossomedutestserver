# vocab/utils.py

import calendar
from django.utils import timezone
from .models import TestResultDetail, MonthlyTestResultDetail, Word, TestResult, PersonalWrongWord

def get_vulnerable_words(profile):
    """
    [수정] 오답률 높은 단어 + 학생이 직접 추가한 오답 단어 병합
    """
    
    # 1. 기존 오답 데이터 수집 (TestResultDetail)
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

    # 오답률 25% 이상인 단어 스펠링
    vulnerable_keys = {text for text, data in stats.items() if data['total'] > 0 and (data['wrong'] / data['total'] >= 0.25)}

    # -------------------------------------------------------------
    # [NEW] 2. 학생이 직접 추가한 오답 단어 가져오기
    # -------------------------------------------------------------
    personal_wrongs = PersonalWrongWord.objects.filter(student=profile).select_related('word')
    for pw in personal_wrongs:
        clean_word = pw.word.english.strip().lower()
        vulnerable_keys.add(clean_word) # 집합에 추가 (중복 자동 제거)
    
    if not vulnerable_keys:
        return []

    # 3. DB에서 후보 단어 가져오기 (english__in)
    # (주의: 스펠링이 같아도 서로 다른 책에 있는 단어가 여러 개일 수 있음)
    candidates = Word.objects.filter(english__in=vulnerable_keys).select_related('book')

    # 4. [정렬] 최근 본 책 우선 (기존 로직 유지)
    recent_tests = TestResult.objects.filter(student=profile).order_by('-created_at').values_list('book_id', flat=True)[:20]
    recent_book_ids = list(dict.fromkeys(recent_tests))

    def get_priority(word):
        if word.book_id in recent_book_ids:
            return recent_book_ids.index(word.book_id)
        return 9999

    sorted_candidates = sorted(candidates, key=get_priority)

    # 5. [중복 제거]
    unique_words = []
    seen_english = set()

    for w in sorted_candidates:
        clean_eng = w.english.strip().lower()
        if clean_eng not in seen_english:
            unique_words.append(w)
            seen_english.add(clean_eng)
    
    return unique_words

def is_monthly_test_period():
    """월말 평가 기간인지 확인 (매달 말일 7일 전부터)"""
    now = timezone.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day > (last_day - 8)