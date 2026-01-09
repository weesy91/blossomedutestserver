from django.urls import path
from . import views

app_name = 'vocab'

urlpatterns = [
    path('', views.index, name='index'),                           # 단어장 선택 (메인)
    path('exam/', views.exam, name='exam'),                        # 시험 화면
    path('save_result/', views.save_result, name='save_result'),   # 결과 저장 API
    path('wrong_study/', views.wrong_answer_study, name='wrong_study'), # 오답 학습 화면
    path('request_correction/', views.request_correction, name='request_correction'), 
    path('result/<int:result_id>/', views.test_result_detail, name='result_detail'),   # 상세 결과표
    path('approve_answer/', views.approve_answer, name='approve_answer'),              # 정답 인정 처리
    
    # [관리자 전용]
    path('admin/result_list/', views.test_result_list, name='test_result_list'),
    path('admin/result_detail/<int:result_id>/', views.test_result_detail, name='test_result_detail'),
    path('approve_answer/', views.approve_answer, name='approve_answer'),
    
    # [추가] 작심 30일 챌린지 확인 페이지
    path('admin/event/check/', views.admin_event_check, name='admin_event_check'),
    
    # [단어 채점 모드] 선생님용 채점 대기 목록
    path('grading/', views.grading_list, name='grading'),
    # 1. [목록] 정정 요청이 있는 '시험지' 목록 (이름순/날짜순 정렬 포함)
    path('grading/', views.grading_list, name='grading_list'),

    # 2. [상세] 특정 시험지(30단어) 채점 화면 
    # test_type은 'normal'(일반/도전) 또는 'monthly'(월말)
    path('grading/<str:test_type>/<int:result_id>/', views.grading_detail, name='grading_detail'),

    # 3. [API] 정답 승인 (기존에 있다면 유지, 없으면 추가)
    path('api/approve/', views.approve_answer, name='approve_answer'),
    
    # 4. [API] 정답 기각 (새로 추가)
    path('api/reject/', views.reject_answer, name='reject_answer'),
    path('api/grading/status/', views.api_check_grading_status, name='api_check_grading_status'),

    # [단어 검색 및 오답 추가]
    path('search/', views.search_word_page, name='search_word_page'),
    path('api/search/', views.api_search_word, name='api_search_word'),
    path('api/add_wrong/', views.api_add_personal_wrong, name='api_add_personal_wrong'),
    path('api/history/date/', views.api_date_history, name='api_date_history'),
    path('my-wrongs/', views.wrong_word_list, name='wrong_word_list'), # [NEW] 오답 목록 페이지
    path('api/chapters/', views.api_get_chapters, name='api_get_chapters'),
]   
