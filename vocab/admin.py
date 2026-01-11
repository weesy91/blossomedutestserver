from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.http import urlencode
from .services import calculate_score

from .models import WordBook, Word, TestResult, TestResultDetail, MonthlyTestResult, MonthlyTestResultDetail, Publisher, RankingEvent

User = get_user_model()

# ==========================================
# 1. 단어장 (WordBook) 관리
# ==========================================
@admin.register(WordBook)
class WordBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'publisher', 'uploaded_by', 'created_at', 'word_list_link')
    search_fields = ('title',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(uploaded_by__is_staff=True).select_related('publisher', 'uploaded_by')

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["queryset"] = User.objects.filter(is_superuser=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def word_list_link(self, obj):
        url = reverse("admin:vocab_word_changelist")
        query = urlencode({"book__id": str(obj.id)})
        count = obj.words.count() 
        return format_html(
            '<a href="{}?{}" class="button" style="background:#79aec8; color:white; padding:5px 10px; border-radius:5px;">📖 단어 {}개 관리하기</a>',
            url, query, count
        )
    word_list_link.short_description = "단어 관리"

# ==========================================
# 2. 단어 (Word) 개별 관리
# ==========================================
@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('english', 'korean', 'book', 'number')
    list_filter = ('book',)
    search_fields = ('english', 'korean')
    list_per_page = 50 

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
# [공통] 답안지 상세 인라인 (Inline) 설정
# ==========================================
class TestResultDetailInline(admin.TabularInline):
    model = TestResultDetail
    extra = 0
    can_delete = False 
    fields = ('word_question', 'correct_answer', 'student_answer', 'is_correct', 'is_resolved')
    readonly_fields = ('word_question', 'correct_answer', 'student_answer')

class MonthlyTestResultDetailInline(admin.TabularInline):
    model = MonthlyTestResultDetail
    extra = 0
    can_delete = False
    fields = ('word_question', 'correct_answer', 'student_answer', 'is_correct')
    readonly_fields = ('word_question', 'correct_answer', 'student_answer')

# ==========================================
# 4. 도전 모드 결과 (TestResult) 관리
# ==========================================
@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at', 'book')
    search_fields = ('student__name', 'book__title') 
    
    # ▼▼▼ [핵심 수정] 아래 한 줄이 빠져 있었습니다! ▼▼▼
    inlines = [TestResultDetailInline]
    
    actions = ['recalculate_scores']

    def get_student_name(self, obj): return obj.student.name  
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj): return obj.book.title if obj.book else "-"
    get_book_title.short_description = "단어장"

    def score_display(self, obj):
        if obj.score >= 27:
            return format_html('<span style="color:green; font-weight:bold;">{}점 (통과)</span>', obj.score)
        return format_html('<span style="color:red; font-weight:bold;">{}점 (재시험)</span>', obj.score)
    score_display.short_description = "점수"

    # [수정] change_view 함수는 삭제했습니다. (inlines가 그 역할을 대신합니다)

    @admin.action(description='선택한 시험 결과 재채점 하기 (수정된 로직 적용)')
    def recalculate_scores(self, request, queryset):
        success_count = 0
        for result in queryset:
            details = result.details.all()
            details_data = []
            for d in details:
                details_data.append({
                    'english': d.word_question,
                    'korean': d.correct_answer,
                    'user_input': d.student_answer
                })
            
            new_score, wrong_count, processed_details = calculate_score(details_data)
            
            result.score = new_score
            result.wrong_count = wrong_count
            result.save()
            
            for db_detail, new_result in zip(details, processed_details):
                if db_detail.is_correct != new_result['c']:
                    db_detail.is_correct = new_result['c']
                    if db_detail.is_correct:
                        db_detail.is_resolved = True 
                    db_detail.save()
            
            success_count += 1
            
        self.message_user(request, f"{success_count}건의 시험 결과를 재채점했습니다.")

# ==========================================
# 5. 월말 평가 결과 (MonthlyTestResult) 관리
# ==========================================
@admin.register(MonthlyTestResult)
class MonthlyTestResultAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'get_book_title', 'score_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('student__name', 'book__title')
    
    # [추가] 월말 평가도 답안을 볼 수 있게 인라인 추가
    inlines = [MonthlyTestResultDetailInline]

    def get_student_name(self, obj): return obj.student.name
    get_student_name.short_description = "학생 이름"

    def get_book_title(self, obj): return obj.book.title if obj.book else "전체 범위"
    get_book_title.short_description = "단어장"

    def score_display(self, obj):
        if obj.score >= 85:
            return format_html('<span style="color:green; font-weight:bold;">{}점 (통과)</span>', obj.score)
        return format_html('<span style="color:red; font-weight:bold;">{}점 (불합격)</span>', obj.score)
    score_display.short_description = "점수"

@admin.register(RankingEvent)
class RankingEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_book', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)