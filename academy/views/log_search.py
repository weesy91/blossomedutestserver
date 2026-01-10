from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from django.utils import timezone
from core.models import StudentProfile
from vocab.models import TestResult
from academy.models import ClassLog, Attendance

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

    # 2. 검색어 필터링
    if query:
        students = base_qs.filter(name__icontains=query).distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')
    else:
        students = base_qs.distinct().annotate(
            last_vocab_date=Max('test_results__created_at')
        ).order_by('name')[:20]

    # 3. 마지막 시험일로부터 경과일(days) 계산
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

@login_required
def student_history(request, student_id):
    """
    [학생 상세 이력]
    - 수업 일지, 출석 기록, 단어 시험 기록 조회
    """
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # 1. 수업 일지 조회
    logs = ClassLog.objects.filter(student=student).order_by('-date')
    
    # 2. 출석 기록 조회
    attendances = Attendance.objects.filter(student=student).order_by('-date')

    # 3. [핵심] 단어 시험 기록 조회 (최신순 20개)
    # create_class_log와 동일하게 prefetch_related 사용 (안전성 확보)
    vocab_results = TestResult.objects.filter(
        student=student
    ).select_related('book').prefetch_related('details').order_by('-created_at')[:20]

    # 디버깅용: 서버 로그에 개수 출력 (필요 시 확인용)
    print(f"--- [DEBUG] {student.name} 단어 기록 개수: {len(vocab_results)} ---")

    # 4. 단어 며칠째 안 봤는지 계산 (헤더 표시용)
    vocab_days = None
    if vocab_results:
        last_date = vocab_results[0].created_at
        diff = timezone.now() - last_date
        vocab_days = diff.days

    return render(request, 'academy/student_history.html', {
        'student': student,
        'logs': logs,
        'attendances': attendances,
        'vocab_results': vocab_results,  # 템플릿 전달
        'vocab_days': vocab_days,
    })