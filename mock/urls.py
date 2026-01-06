# mock/urls.py
from django.urls import path
from . import views

app_name = 'mock'

urlpatterns = [
    path('list/', views.student_list, name='student_list'),
    path('input/<int:student_id>/', views.input_score, name='input_score'),
    path('bulk-upload/', views.bulk_omr_upload, name='bulk_upload'),
]