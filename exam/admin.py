from django.contrib import admin
from .models import Question, TestPaper, ExamResult, QuestionUpload
from django.shortcuts import redirect

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('textbook', 'chapter', 'number', 'category', 'style')
    list_filter = ('category', 'textbook')
    search_fields = ('textbook__title', 'question_text')

class QuestionInline(admin.TabularInline):
    model = TestPaper.questions.through
    extra = 1

@admin.register(TestPaper)
class TestPaperAdmin(admin.ModelAdmin):
    # student -> StudentProfile
    list_display = ('title', 'get_student_name', 'created_at')
    search_fields = ('title', 'student__name')
    exclude = ('questions',) # M2M 필드는 일반 필드에서 제외하고
    inlines = [QuestionInline] # 인라인으로 관리하거나 별도 로직 사용

    def get_student_name(self, obj):
        return obj.student.name
    get_student_name.short_description = "배정 학생"

@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('date', 'get_student_name', 'paper', 'score')
    list_filter = ('date', 'paper')
    
    def get_student_name(self, obj):
        return obj.student.name
    get_student_name.short_description = "학생 이름"

# [NEW] 문제 대량 업로드 바로가기 메뉴
@admin.register(QuestionUpload)
class QuestionUploadAdmin(admin.ModelAdmin):
    """
    이 메뉴를 클릭하면 리스트 화면 대신 '이미지 업로드 페이지'로 리다이렉트됩니다.
    """
    def changelist_view(self, request, extra_context=None):
        return redirect('exam:upload_images')
        
    def has_add_permission(self, request):
        return False # '추가' 버튼 숨김
        
    def has_change_permission(self, request, obj=None):
        return False # '수정' 권한 없음 (메뉴만 보이게)
        
    # 슈퍼유저만 메뉴가 보이게 하려면 아래 주석 해제
    def has_module_permission(self, request):
        return request.user.is_superuser