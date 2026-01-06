from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages # 👈 추가
from django.utils import timezone 
from django.urls import reverse_lazy
import calendar 

# [핵심 수정] 아래 임포트들이 반드시 있어야 에러가 나지 않습니다.
from django.db.models import Q, Max 
from datetime import timedelta, time
from .models import StudentProfile, ClassTime
from academy.models import Attendance, TemporarySchedule, ClassLog

def login_view(request):
    """로그인 페이지 처리"""
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('core:teacher_home')
        return redirect('vocab:index')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('core:login_dispatch') 
    else:
        form = AuthenticationForm()
    
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    """로그아웃 처리"""
    logout(request)
    return redirect('core:login')

@login_required(login_url='core:login')
def index(request):
    """메인 대시보드"""
    return render(request, 'core/index.html', {
        'user': request.user
    })

def login_dispatch(request):
    print(f"로그인 감지! 사용자: {request.user}, 슈퍼유저여부: {request.user.is_superuser}")

    if request.user.is_superuser:
        return redirect('admin:index')
    
    # 선생님(스태프)이면 선생님 홈으로
    if request.user.is_staff:
        return redirect('core:teacher_home')
        
    # [변경] 학생이면 '학생 홈'으로 이동
    return redirect('core:student_home')

@login_required(login_url='core:login')
def teacher_home(request):
    """선생님 메인 허브"""
    if not request.user.is_staff:
        return redirect('vocab:index')
    
    now = timezone.now()
    
    # [NEW] 단어 시험 오랫동안 안 본 학생 체크 (대시보드 알림용)
    # 1. 내 담당 학생 조회
    my_students = StudentProfile.objects.filter(
        Q(syntax_teacher=request.user) | Q(reading_teacher=request.user) | Q(extra_class_teacher=request.user)
    ).distinct().annotate(
        last_test_dt=Max('test_results__created_at')
    )
    
    # 2. 5일 이상 미응시자 카운트
    danger_limit = now - timedelta(days=5)
    warning_count = 0
    
    for s in my_students:
        # 시험 기록이 아예 없거나, 마지막 시험이 5일 이전인 경우
        if not s.last_test_dt or s.last_test_dt < danger_limit:
            warning_count += 1

    # 기존 월말평가 기간 계산 로직
    last_day = calendar.monthrange(now.year, now.month)[1]
    start_day = last_day - 7
    is_exam_period = (now.day >= start_day)

    context = {
        'is_exam_period': is_exam_period,
        'vocab_warning_count': warning_count, # 템플릿으로 전달
    }
    
    return render(request, 'core/teacher_home.html', context)

# 👇 [추가] 비밀번호 변경 뷰
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'core/password_change.html'
    success_url = reverse_lazy('core:student_home')
    
    def form_valid(self, form):
        messages.success(self.request, "비밀번호가 성공적으로 변경되었습니다! 🎉")
        return super().form_valid(form)
    
@login_required(login_url='core:login')
def student_home(request):
    """
    학생용 메인 대시보드
    """
    user = request.user
    today = timezone.now().date()
    
    # 1. 학생 프로필 확인 (없으면 로그인 화면으로 튕겨냄)
    if not hasattr(user, 'profile'):
        return redirect('core:login')
    
    profile = user.profile
    
    # ==========================================
    # [1] 오늘 수업 시간표 구하기 (복잡한 로직)
    # ==========================================
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    today_code = weekday_map[today.weekday()]
    
    schedules = []

    # 1-1. 정규 수업 (구문/독해/추가)
    # -> 오늘 요일에 해당하는 수업이 있는지 확인
    # -> 단, "오늘 날짜로 보강이 잡혀서 다른 날로 이동한 경우(moved_away)"는 제외해야 함
    
    # (A) 구문 수업
    if profile.syntax_class and profile.syntax_class.day == today_code:
        is_moved = TemporarySchedule.objects.filter(
            student=profile, original_date=today, subject='SYNTAX'
        ).exists()
        if not is_moved:
            schedules.append({
                'type': '정규',
                'subject': '구문',
                'time': profile.syntax_class,
                'teacher': profile.syntax_teacher
            })

    # (B) 독해 수업
    if profile.reading_class and profile.reading_class.day == today_code:
        is_moved = TemporarySchedule.objects.filter(
            student=profile, original_date=today, subject='READING'
        ).exists()
        if not is_moved:
            schedules.append({
                'type': '정규',
                'subject': '독해',
                'time': profile.reading_class,
                'teacher': profile.reading_teacher
            })

    # (C) 추가 수업
    if profile.extra_class and profile.extra_class.day == today_code:
        # 추가 수업은 보통 이동 개념이 없으므로 그대로 표시
        label = f"{profile.get_extra_class_type_display()} (추가)"
        schedules.append({
            'type': '추가',
            'subject': label,
            'time': profile.extra_class,
            'teacher': profile.extra_class_teacher
        })

    # 1-2. 보강/일정변경 (오늘 날짜로 새로 잡힌 수업)
    temp_schedules = TemporarySchedule.objects.filter(student=profile, new_date=today)
    for ts in temp_schedules:
        # 선생님 정보 찾기
        teacher = None
        if ts.subject == 'SYNTAX': teacher = profile.syntax_teacher
        elif ts.subject == 'READING': teacher = profile.reading_teacher
        
        # 라벨 설정 (보강 vs 일정변경)
        label_type = "보강" if ts.is_extra_class else "변경됨"
        
        schedules.append({
            'type': label_type,
            'subject': ts.get_subject_display(),
            'time_obj': ts, # 템플릿에서 start_time 처리를 위해 객체 통째로 넘김
            'start_time': ts.new_start_time, # 정렬용
            'teacher': teacher
        })

    # 1-3. 시간순 정렬 (정규 수업은 class_time.start_time, 보강은 new_start_time 기준)
    def get_start_time(item):
        if 'start_time' in item: return item['start_time']
        return item['time'].start_time
    
    schedules.sort(key=get_start_time)


    # ==========================================
    # [2] 출석 현황 (오늘)
    # ==========================================
    attendance = Attendance.objects.filter(student=user, date=today).first()


    # ==========================================
    # [3] 최신 과제 (숙제) 가져오기
    # ==========================================
    # 가장 최근에 작성된 일지를 가져옵니다. (오늘 작성된 게 있다면 오늘 것, 아니면 지난 수업 것)
    last_log = ClassLog.objects.filter(student=user).order_by('-date', '-created_at').first()


    return render(request, 'core/student_home.html', {
        'profile': profile,
        'today': today,
        'schedules': schedules,
        'attendance': attendance,
        'last_log': last_log,
    })