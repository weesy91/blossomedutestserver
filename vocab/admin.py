from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404
from .models import WordBook, Word, TestResult, TestResultDetail, MonthlyTestResult, MonthlyTestResultDetail, Publisher, RankingEvent
from django.contrib.auth import get_user_model
User = get_user_model()

# ==========================================
# 1. 단어장 (WordBook) 관리
# ==========================================
class WordInline(admin.TabularInline):
    model = Word
    extra = 3

@admin.register(WordBook)
class WordBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'publisher', 'uploaded_by', 'created_at')
    search_fields = ('title',)
    inlines = [WordInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('publisher', 'uploaded_by')

    # [수정 1] 등록자를 선택하지 않았을 때 현재 로그인한 관리자로 자동 저장
    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    # [수정 2] 등록자 선택 목록에서 슈퍼유저만 보이게 필터링 (return 추가)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["queryset"] = User.objects.filter(is_superuser=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# ==========================================
# 2. 출판사 (Publisher) 관리
# ==========================================
@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name',)

    # 팝업 저장 후 자동 닫기 로직
    def response_add(self, request, obj, post_url_continue=None):
        if "_popup" in request.POST:
            return HttpResponse('''
                <script type="text/javascript">
                    window.close();
                    if (window.opener && !window.opener.closed) {
                        window.opener.location.reload();
                    }
                </script>
            ''')
        return super().response_add(request, obj, post_url_continue)

# ==========================================
# 3. 도전 모드 결과 (TestResult) 관리
# ==========================================
@admin.register(TestResult) # [수정됨] 중복 데코레이터 제거 완료!
class TestResultAdmin(admin.ModelAdmin):
    # student는 이제 StudentProfile 객체입니다.
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at', 'book')
    search_fields = ('student__name', 'book__title') 

    def get_student_name(self, obj):
        return obj.student.name  
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj):
        return obj.book.title if obj.book else "-"
    get_book_title.short_description = "단어장"

    # 점수에 색깔 넣기 기능 유지
    def score_display(self, obj):
        if obj.score >= 27:
            return format_html('<span style="color:green; font-weight:bold;">{}점 (통과)</span>', obj.score)
        return format_html('<span style="color:red; font-weight:bold;">{}점 (재시험)</span>', obj.score)
    score_display.short_description = "점수"

    # 상세 페이지 커스텀 뷰 유지 (단, 템플릿 파일이 존재해야 함)
    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            result = get_object_or_404(TestResult, pk=object_id)
            details = TestResultDetail.objects.filter(result=result).order_by('id')
            
            context = {
                'result': result,
                'details': details,
                'opts': self.model._meta,
                'has_view_permission': True,
                # 뒤로가기 링크가 깨지지 않도록 수정
                'back_url': '/admin/vocab/testresult/' 
            }
            return render(request, 'vocab/admin_result_detail.html', context)
        except Exception as e:
            # 혹시 템플릿 오류가 나면 기본 화면이라도 보여주도록 안전장치
            return super().change_view(request, object_id, form_url, extra_context)

# ==========================================
# 4. 월말 평가 결과 (MonthlyTestResult) 관리
# ==========================================
@admin.register(MonthlyTestResult)
class MonthlyTestResultAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('student__name', 'book__title') # [수정] 검색 필드 경로 수정

    def get_student_name(self, obj):
        return obj.student.name
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj):
        return obj.book.title if obj.book else "전체 범위"
    get_book_title.short_description = "단어장"

    def score_display(self, obj):
        if obj.score >= 85:
            return format_html('<span style="color:green; font-weight:bold;">{}점 (통과)</span>', obj.score)
        return format_html('<span style="color:red; font-weight:bold;">{}점 (불합격)</span>', obj.score)
    score_display.short_description = "점수"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            result = get_object_or_404(MonthlyTestResult, pk=object_id)
            details = MonthlyTestResultDetail.objects.filter(result=result).order_by('id')
            
            context = {
                'result': result,
                'details': details,
                'opts': self.model._meta,
                'has_view_permission': True,
                'back_url': '/admin/vocab/monthlytestresult/'
            }
            return render(request, 'vocab/admin_result_detail.html', context)
        except:
             return super().change_view(request, object_id, form_url, extra_context)
        
@admin.register(RankingEvent)
class RankingEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_book', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',) # 목록에서 바로 켜고 끌 수 있게