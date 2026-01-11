from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from django.utils import timezone
from core.models import StudentProfile
from vocab.models import TestResult  # ★ 모델 임포트 필수
from academy.models import ClassLog, Attendance

@login_required
def log_search(request):
    """
    [로그 검색] 학생 이름을 검색하여 과거 수업 일지(History)로 이동하는 관문 페이지
    """
    query = request.GET.get('q', '').strip()
    user = request.user
    students = StudentProfile.objects.none()

    # 1. 권한별 학생 필터링
    if user.is_superuser:
        base_qs = StudentProfile.objects.all()
    elif hasattr(user, 'staff_profile') and user.staff_profile.position == 'VICE':
        managed_teachers = user.staff_profile.managed_teachers.all()
        team_teachers = list(managed_teachers) + [user]
        base_qs = StudentProfile.objects.filter(
            Q(syntax_teacher__in=team_teachers) | 
            Q(reading_teacher__in=team_teachers) |
            Q(extra_class_teacher__in=team_teachers)
        )
    else:
        base_qs = StudentProfile.objects.filter(
            Q(syntax_teacher=user) | 
            Q(reading_teacher=user) | 
            Q(extra_class_teacher=user)
        )

    # 2. 검색어 필터링
    if query:
        students = base_qs.filter(name__icontains=query).distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')
    else:
        students = base_qs.distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')[:20]

    # 3. 경과일 계산
    now = timezone.now()
    student_list = []
    for s in students:
        s.vocab_days = None
        if s.last_vocab_date:
            diff = now - s.last_vocab_date
            s.vocab_days = diff.days
        student_list.append(s)

    return render(request, 'academy/log_search.html', {
        'students': student_list,
        'query': query
    })

# ▼▼▼ [중요] 이 함수가 빠져 있었습니다! 꼭 추가해주세요 ▼▼▼
@login_required
def student_history(request, student_id):
    """
    [학생 상세 이력] 수업 일지 + 단어 시험 기록 조회
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # 1. 수업 일지 조회
    logs = ClassLog.objects.filter(student=student).order_by('-date')
    
    # 2. 출석 기록 조회
    attendances = Attendance.objects.filter(student=student).order_by('-date')

    # 3. 단어 시험 기록 조회 (vocab/models.py 확인 결과 student 필드가 맞음)
    vocab_results = TestResult.objects.filter(
        student=student
    ).select_related('book').prefetch_related('details').order_by('-created_at')[:20]

    # 4. 단어 며칠째 안 봤는지 계산
    vocab_days = None
    if vocab_results:
        last_date = vocab_results[0].created_at
        diff = timezone.now() - last_date
        vocab_days = diff.days

    return render(request, 'academy/student_history.html', {
        'student': student,
        'logs': logs,
        'attendances': attendances,
        'vocab_results': vocab_results,  # 템플릿으로 전달
        'vocab_days': vocab_days,
    })