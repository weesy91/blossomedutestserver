from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import get_user_model
# [필수] 링크 생성 및 유틸 함수 import
from django.urls import reverse
from django.utils.http import urlencode

from .models import WordBook, Word, TestResult, TestResultDetail, MonthlyTestResult, MonthlyTestResultDetail, Publisher, RankingEvent

User = get_user_model()

# ==========================================
# 1. 단어장 (WordBook) 관리
# ==========================================

# [중요] 1600개 단어 로딩 렉 방지를 위해 인라인은 주석 처리 또는 삭제합니다.
# class WordInline(admin.TabularInline):
#     model = Word
#     extra = 3

@admin.register(WordBook)
class WordBookAdmin(admin.ModelAdmin):
    # 'word_list_link'를 추가하여 목록에서 바로 단어 관리 페이지로 이동
    list_display = ('title', 'publisher', 'uploaded_by', 'created_at', 'word_list_link')
    search_fields = ('title',)
    
    # [중요] 상세 페이지 들어갈 때 렉 걸리지 않도록 inlines 제거
    # inlines = [WordInline] 

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('publisher', 'uploaded_by')

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["queryset"] = User.objects.filter(is_superuser=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # [핵심 기능] 단어 관리 버튼 생성
    def word_list_link(self, obj):
        # 1. 단어 목록 페이지 URL 가져오기
        url = reverse("admin:vocab_word_changelist")
        # 2. 현재 단어장(obj.id)에 속한 단어만 필터링하는 쿼리 생성
        query = urlencode({"book__id": str(obj.id)})
        # 3. 모델의 related_name='words'를 사용하여 개수 세기
        count = obj.words.count() 
        
        return format_html(
            '<a href="{}?{}" class="button" style="background:#79aec8; color:white; padding:5px 10px; border-radius:5px;">📖 단어 {}개 관리하기</a>',
            url, query, count
        )
    
    word_list_link.short_description = "단어 관리"

# ==========================================
# 2. 단어 (Word) 개별 관리 - 페이징 처리됨
# ==========================================
@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('english', 'korean', 'book', 'number')
    list_filter = ('book',) # 필터 메뉴에서 단어장을 고를 수 있음
    search_fields = ('english', 'korean')
    list_per_page = 50 # [핵심] 한 페이지에 50개씩만 보여줘서 렉 해결!

# ==========================================
# 3. 출판사 (Publisher) 관리
# ==========================================
@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name',)
    def response_add(self, request, obj, post_url_continue=None):
        if "_popup" in request.POST:
            return HttpResponse('''
                <script type="text/javascript">
                    window.close();
                    if (window.opener && !window.opener.closed) { window.opener.location.reload(); }
                </script>
            ''')
        return super().response_add(request, obj, post_url_continue)

# ==========================================
# 4. 도전 모드 결과 (TestResult) 관리
# ==========================================
@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at', 'book')
    search_fields = ('student__name', 'book__title') 

    def get_student_name(self, obj): return obj.student.name  
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj): return obj.book.title if obj.book else "-"
    get_book_title.short_description = "단어장"

    def score_display(self, obj):
        if obj.score >= 27:
            return format_html('<span style="color:green; font-weight:bold;">{}점 (통과)</span>', obj.score)
        return format_html('<span style="color:red; font-weight:bold;">{}점 (재시험)</span>', obj.score)
    score_display.short_description = "점수"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        try:
            result = get_object_or_404(TestResult, pk=object_id)
            details = TestResultDetail.objects.filter(result=result).order_by('id')
            context = {'result': result, 'details': details, 'opts': self.model._meta, 'has_view_permission': True, 'back_url': '/admin/vocab/testresult/'}
            return render(request, 'vocab/admin_result_detail.html', context)
        except: return super().change_view(request, object_id, form_url, extra_context)

# ==========================================
# 5. 월말 평가 결과 (MonthlyTestResult) 관리
# ==========================================
@admin.register(MonthlyTestResult)
class MonthlyTestResultAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('student__name', 'book__title')

    def get_student_name(self, obj): return obj.student.name
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj): return obj.book.title if obj.book else "전체 범위"
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
            context = {'result': result, 'details': details, 'opts': self.model._meta, 'has_view_permission': True, 'back_url': '/admin/vocab/monthlytestresult/'}
            return render(request, 'vocab/admin_result_detail.html', context)
        except: return super().change_view(request, object_id, form_url, extra_context)

@admin.register(RankingEvent)
class RankingEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_book', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)