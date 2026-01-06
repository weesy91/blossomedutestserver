# reports/admin.py

from django.contrib import admin
from .models import MonthlyReport

@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('student', 'year', 'month', 'total_days', 'vocab_average_score', 'created_at')
    list_filter = ('year', 'month', 'student__branch', 'student__school')
    search_fields = ('student__name', 'overall_comment')
    readonly_fields = ('access_code', 'created_at')
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('student', 'year', 'month', 'access_code', 'created_at')
        }),
        ('출결 현황', {
            'fields': ('total_days', 'present_days', 'late_days', 'absent_days', 'makeup_count', 'unexcused_absent')
        }),
        ('어휘 학습', {
            'fields': ('vocab_progress_info', 'vocab_test_count', 'vocab_pass_count', 'vocab_fail_count', 'vocab_average_score')
        }),
        ('수업 및 평가', {
            'fields': ('study_summary', 'textbook_progress', 'performance_comment', 'exam_score_vocab', 'exam_score_syntax', 'exam_score_reading', 'class_average_score', 'overall_comment')
        }),
    )