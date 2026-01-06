from django.contrib import admin
from django.http import HttpResponse
from django import forms
from django.contrib.auth import get_user_model
# core 모델들도 import 해야 합니다!
from core.models import StudentProfile, ClassTime 
from .models import TemporarySchedule, Attendance, Textbook, TextbookUnit, ClassLog, ClassLogEntry

User = get_user_model()

# ==========================================
# [공통 함수] 팝업 강제 종료 및 부모창 새로고침
# ==========================================
def force_close_popup(request, obj, post_url_continue=None):
    if "_popup" in request.POST:
        return HttpResponse('<script>window.close(); if(window.opener) window.opener.location.reload();</script>')
    return None 

# ==========================================
# [1] 출석 관리 (Attendance)
# ==========================================
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    # student는 이제 Profile 객체이므로, 이름 표시를 위해 __name 사용
    list_display = ('date', 'get_student_name', 'status', 'check_in_time')
    list_filter = ('date', 'status', 'student__branch') # 지점별 필터 가능!

    def get_student_name(self, obj):
        return obj.student.name
    get_student_name.short_description = "학생 이름"

    # 팝업 저장 시 강제 닫기 적용
    def response_add(self, request, obj, post_url_continue=None):
        return force_close_popup(request, obj, post_url_continue) or \
               super().response_add(request, obj, post_url_continue)

# ==========================================
# [2] 보강/일정 관리 (TemporarySchedule)
# ==========================================
@admin.register(TemporarySchedule)
class TemporaryScheduleAdmin(admin.ModelAdmin):
    # 1. 목록 화면
    list_display = ('student', 'get_subject_display', 'is_extra_class', 'original_date', 'new_date', 'new_start_time')
    
    # 2. 입력 화면 설정
    fields = (
        'student', 
        'subject', 
        'is_extra_class', 
        'original_date', 
        'new_date', 
        'target_class', 
        'note'
    )

    # 3. 학생 검색 기능
    autocomplete_fields = ['student']

    # 4. 자바스크립트 연결 (필요시 사용)
    class Media:
        js = ('admin/js/schedule_filter.js',)

    # 5. 드롭다운 필터링
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "target_class":
            kwargs["queryset"] = ClassTime.objects.order_by('day', 'start_time')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # 과목명 한글 표시
    def get_subject_display(self, obj):
        return obj.get_subject_display()
    get_subject_display.short_description = "과목"

    # 팝업 닫기 처리
    def response_add(self, request, obj, post_url_continue=None):
        return force_close_popup(request, obj, post_url_continue) or \
               super().response_add(request, obj, post_url_continue)
    
# ==========================================
# [3] 교재 관리 (Textbook)
# ==========================================
class TextbookUnitInline(admin.TabularInline):
    model = TextbookUnit
    extra = 1
    fields = ('unit_number', 'link_url')
    verbose_name = "단원 링크"
    verbose_name_plural = "단원 링크"

@admin.register(Textbook)
class TextbookAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'total_units', 'publisher')
    list_filter = ('category', 'publisher')
    search_fields = ('title', 'publisher')
    ordering = ('category', 'title')
    inlines = [TextbookUnitInline]
    
    def response_add(self, request, obj, post_url_continue=None):
        return force_close_popup(request, obj, post_url_continue) or \
               super().response_add(request, obj, post_url_continue)
    
# ==========================================
# [4] 수업 일지 (ClassLog & Entry)
# ==========================================
class ClassLogEntryInline(admin.TabularInline):
    model = ClassLogEntry
    extra = 1
    fields = ('textbook', 'wordbook', 'progress_range', 'score')
    verbose_name = "수업 진도 항목"
    verbose_name_plural = "수업 진도 항목"

class StudentChoiceField(forms.ModelChoiceField):
    """학생 이름과 학교명을 표시하는 커스텀 필드"""
    def label_from_instance(self, obj):
        # obj는 이제 StudentProfile 객체입니다!
        school_name = obj.school.name if obj.school else "학교 미정"
        return f"{obj.name} ({school_name})"

class ClassLogAdminForm(forms.ModelForm):
    """ClassLog Admin Form - Student 필드 커스터마이징"""
    # [수정됨] queryset을 User가 아니라 StudentProfile로 변경
    student = StudentChoiceField(
        queryset=StudentProfile.objects.select_related('school'),
        label='학생',
        required=True
    )
    
    class Meta:
        model = ClassLog
        fields = '__all__'

@admin.register(ClassLog)
class ClassLogAdmin(admin.ModelAdmin):
    form = ClassLogAdminForm
    # [수정됨] get_student_name 메서드를 사용하도록 변경
    list_display = ('date', 'get_student_display', 'subject', 'get_teacher_name')
    # [수정됨] 검색 필드 경로 변경 (student는 이제 profile이므로 바로 name 접근)
    search_fields = ('student__name', 'comment') 
    ordering = ('-date', '-created_at')
    inlines = [ClassLogEntryInline]
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('student', 'date', 'teacher', 'comment')
        }),
    )

    def get_student_display(self, obj):
        """학생 이름과 학교명을 표시"""
        # [수정됨] obj.student가 이미 profile입니다.
        profile = obj.student 
        school_name = profile.school.name if profile.school else "학교 미정"
        return f"{profile.name} ({school_name})"
    get_student_display.short_description = "학생"
    
    def get_teacher_name(self, obj):
        if obj.teacher:
            # 선생님은 여전히 User 모델이므로 profile을 타고 들어가야 함
            return obj.teacher.staff_profile.name if hasattr(obj.teacher, 'staff_profile') else obj.teacher.username
        return "-"
    get_teacher_name.short_description = "선생님"

    def response_add(self, request, obj, post_url_continue=None):
        return force_close_popup(request, obj, post_url_continue) or \
               super().response_add(request, obj, post_url_continue)