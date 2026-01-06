from django.urls import path
from . import views, views_api, views_upload, views_wizard, views_test, views_grading

app_name = 'exam'

urlpatterns = [
    # 1. 마법사 화면
    path('wizard/', views_wizard.exam_wizard, name='exam_wizard'),
    
    # 2. 문제 검색 API [수정됨!] 
    # views_wizard -> views_api 로 변경하고 함수 이름도 get_questions_api로 맞춰주세요
    path('api/questions/', views_api.get_questions_api, name='api_get_questions'),
    
    path('api/students/', views_api.get_students_by_teacher, name='get_students_by_teacher'),

    # 3. 시험지 생성 및 출력
    path('create/', views.create_test_paper, name='exam_create'),
    path('print/<int:paper_id>/', views.print_test_paper, name='print_test_paper'),

    # 4. 이미지 업로드
    path('upload/', views_upload.upload_images_bulk, name='upload_images'),

    path('grading/', views_grading.grading_list, name='grading_list'),
    path('grading/<int:paper_id>/', views_grading.grading_form, name='grading_form'),
]