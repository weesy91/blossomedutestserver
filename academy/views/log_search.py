from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from core.models import StudentProfile
from django.utils import timezone

@login_required
def log_search(request):
    """
    [로그 검색] 학생 이름을 검색하여 과거 수업 일지(History)로 이동하는 관문 페이지
    - 권한: 원장(전체), 부원장(본인+팀원), 강사(본인 담당)
    """
    query = request.GET.get('q', '').strip()
    user = request.user
    students = StudentProfile.objects.none()

    # 1. 권한별 학생 필터링 (Base QuerySet)
    if user.is_superuser:
        base_qs = StudentProfile.objects.all()
    elif hasattr(user, 'staff_profile') and user.staff_profile.position == 'VICE':
        # 부원장: 본인 + 관리하는 강사들의 학생
        managed_teachers = user.staff_profile.managed_teachers.all()
        team_teachers = list(managed_teachers) + [user]
        base_qs = StudentProfile.objects.filter(
            Q(syntax_teacher__in=team_teachers) | 
            Q(reading_teacher__in=team_teachers) |
            Q(extra_class_teacher__in=team_teachers)
        )
    else:
        # 일반 강사: 본인 담당 학생
        base_qs = StudentProfile.objects.filter(
            Q(syntax_teacher=user) | 
            Q(reading_teacher=user) | 
            Q(extra_class_teacher=user)
        )

    # 2. 검색어 필터링 (검색어가 있을 때만 동작)
    if query:
        # annotate 추가
        students = base_qs.filter(name__icontains=query).distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')
    else:
        # annotate 추가
        students = base_qs.distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')[:20]

    # [수정 2] 파이썬 레벨에서 days 계산해서 객체에 '속성'으로 붙여주기
    # (템플릿에서 복잡한 계산을 안 하기 위해 여기서 미리 계산합니다)
    now = timezone.now()
    
    # 쿼리셋을 리스트로 변환하며 속성 주입 (이 방식이 템플릿에서 쓰기 가장 편함)
    student_list = []
    for s in students:
        s.vocab_days = None # 기본값
        if s.last_vocab_date:
            diff = now - s.last_vocab_date
            s.vocab_days = diff.days
        student_list.append(s)

    # 렌더링 시 students 대신 student_list 전달
    return render(request, 'academy/log_search.html', {
        'students': student_list, # 수정됨
        'query': query
    })