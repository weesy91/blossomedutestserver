from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone 
import calendar 

# [핵심 수정] 아래 임포트들이 반드시 있어야 에러가 나지 않습니다.
from django.db.models import Q, Max 
from datetime import timedelta
from .models import StudentProfile

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
    """로그인 후 역할에 따라 페이지 분배"""
    user = request.user
    if user.is_staff:
        return redirect('core:teacher_home')
    return redirect('vocab:index')

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