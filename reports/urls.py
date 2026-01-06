# reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # 선생님이 성적표 생성하는 URL (버튼 클릭용)
    path('dashboard/', views.report_dashboard, name='dashboard'),
    path('create/<int:student_id>/', views.create_monthly_report, name='create'),
    path('view/<uuid:access_code>/', views.report_view, name='view'),
]