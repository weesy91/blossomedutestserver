from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.utils import timezone
from .models import MonthlyReport
from core.models import StudentProfile
from academy.models import Attendance, ClassLog
from vocab.models import TestResult, MonthlyTestResult
from exam.models import ExamResult
from mock.models import MockExam
import json

@login_required
def create_monthly_report(request, student_id):
    """
    [선생님용] 특정 학생의 이번 달 성적표 데이터를 긁어와서 생성/갱신하는 함수
    """
    student_profile = get_object_or_404(StudentProfile, id=student_id)
    
    # 기준 연월 (오늘 날짜 기준)
    now = timezone.now()
    year = now.year
    month = now.month

    # 1. 이미 생성된 게 있으면 가져오고, 없으면 새로 만듦
    report, created = MonthlyReport.objects.get_or_create(
        student=student_profile,
        year=year,
        month=month
    )

    # ==========================================
    # Part 1. 출결 데이터 집계 (Attendance)
    # ==========================================
    # [수정] student=student_profile (User 객체 아님)
    attendances = Attendance.objects.filter(
        student=student_profile, 
        date__year=year, 
        date__month=month
    )
    
    report.total_days = attendances.count()
    report.present_days = attendances.filter(status='PRESENT').count()
    report.late_days = attendances.filter(status='LATE').count()
    report.absent_days = attendances.filter(status='ABSENT').count()
    
    # ==========================================
    # Part 2. 어휘 학습 데이터 (Vocab)
    # ==========================================
    # [수정] student=student_profile
    vocab_results = TestResult.objects.filter(
        student=student_profile,
        created_at__year=year,
        created_at__month=month
    )
    
    report.vocab_test_count = vocab_results.count()
    report.vocab_pass_count = vocab_results.filter(score__gte=27).count() 
    report.vocab_fail_count = report.vocab_test_count - report.vocab_pass_count
    
    avg_score = vocab_results.aggregate(Avg('score'))['score__avg']
    report.vocab_average_score = round(avg_score, 1) if avg_score else 0.0

    # ==========================================
    # Part 3. 월말평가 점수 (Exam & Vocab Monthly)
    # ==========================================
    # 1) 단어 월말평가 (student=student_profile)
    monthly_vocab = MonthlyTestResult.objects.filter(
        student=student_profile, created_at__year=year, created_at__month=month
    ).last()
    
    if monthly_vocab:
        report.exam_score_vocab = monthly_vocab.score

    # 2) 구문/독해 월말평가 (ExamResult)
    # [수정] ExamResult도 student가 Profile입니다.
    monthly_exams = ExamResult.objects.filter(
        student=student_profile, date__year=year, date__month=month
    )
    
    # 여러 번 봤을 수 있으므로, 가장 최근 것 중 '구문', '독해' 타이틀로 구분
    for exam in monthly_exams:
        title = exam.paper.title
        if '구문' in title or 'Syntax' in title:
            report.exam_score_syntax = exam.score
        elif '독해' in title or 'Reading' in title:
            report.exam_score_reading = exam.score
            
    report.save()
    
    return redirect('reports:view', access_code=report.access_code)


def report_view(request, access_code):
    """
    [학부모/학생용] 로그인 없이 UUID 코드로 성적표 보기
    """
    report = get_object_or_404(MonthlyReport, access_code=access_code)
    student = report.student
    
    # 1. 수업 일지 가져오기
    logs = ClassLog.objects.filter(
        student=student,
        date__year=report.year,
        date__month=report.month
    ).order_by('-date')

    # 2. [추가] 모의고사 데이터 가져오기 (최근 6개월 추세 확인용)
    # 해당 월뿐만 아니라 전체적인 흐름을 보여주기 위해 기간을 넉넉히 잡거나 전체를 가져옵니다.
    mock_exams = MockExam.objects.filter(student=student).order_by('exam_date')
    
    # 그래프용 데이터 가공 (JSON 변환)
    dates = [e.exam_date.strftime("%m/%d") for e in mock_exams]
    scores = [e.score for e in mock_exams]
    grades = [e.grade for e in mock_exams]
    titles = [e.title for e in mock_exams]

    context = {
        'report': report,
        'student': student,
        'logs': logs,
        # [추가] 모의고사 데이터
        'mock_exams': mock_exams.reverse(), # 리스트는 최신순 표시
        'graph_dates': json.dumps(dates),
        'graph_scores': json.dumps(scores),
        'graph_grades': json.dumps(grades),
        'graph_titles': json.dumps(titles),
    }
    return render(request, 'reports/report_card.html', context)

@login_required
def report_dashboard(request):
    """
    [선생님용] 성적표 관리 대시보드
    """
    now = timezone.now()
    year = now.year
    month = now.month
    
    user = request.user
    
    # [권한 분리] 
    # 1. 슈퍼유저/원장: 전체 학생 조회
    # 2. 부원장: 본인 팀 + 본인 학생
    # 3. 일반 강사: 본인 담당 학생만 조회
    
    if user.is_superuser:
        students = StudentProfile.objects.all().order_by('name')
    elif hasattr(user, 'staff_profile'):
        profile = user.staff_profile
        if profile.position == 'VICE':
            # 관리하는 강사들의 학생까지 포함 (복잡하므로 일단 본인 담당만 하거나 팀원 로직 추가)
            team_teachers = list(profile.managed_teachers.all()) + [user]
            students = StudentProfile.objects.filter(
                Q(syntax_teacher__in=team_teachers) | 
                Q(reading_teacher__in=team_teachers) |
                Q(extra_class_teacher__in=team_teachers)
            ).distinct().order_by('name')
        else:
            # 일반 강사
            students = StudentProfile.objects.filter(
                Q(syntax_teacher=user) | 
                Q(reading_teacher=user) | 
                Q(extra_class_teacher=user)
            ).distinct().order_by('name')
    else:
        students = StudentProfile.objects.none()

    dashboard_data = []
    for student in students:
        report = MonthlyReport.objects.filter(
            student=student, 
            year=year, 
            month=month
        ).first()
        
        dashboard_data.append({
            'student': student,
            'report': report,
        })

    context = {
        'year': year,
        'month': month,
        'dashboard_data': dashboard_data
    }
    return render(request, 'reports/dashboard.html', context)