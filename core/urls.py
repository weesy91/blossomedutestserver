from django.urls import path
from . import views

app_name = 'core'  # [중요] 나중에 'core:login' 처럼 부르기 위해 필요

urlpatterns = [
    path('', views.index, name='index'),        # 메인 화면
    path('login/', views.login_view, name='login'), # 로그인
    path('logout/', views.logout_view, name='logout'), # 로그아웃
    path('teacher-home/', views.teacher_home, name='teacher_home'), # 선생님 메인 허브
    path('dispatch/', views.login_dispatch, name='login_dispatch'),
    # 👇 [추가] 학생 홈 & 비밀번호 변경
    path('student-home/', views.student_home, name='student_home'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('api/get-classtimes/', views.get_classtimes_with_availability, name='get_classtimes_with_availability'),
]