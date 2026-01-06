# mock/admin.py
from django.contrib import admin
from .models import MockExamInfo, MockExamQuestion, MockExam

# 1. 문항(Questions)을 모의고사 정보 안에서 바로 수정하기 위한 인라인 설정
class QuestionInline(admin.TabularInline):
    model = MockExamQuestion
    extra = 0
    # 문항번호는 실수로 수정하지 않게 읽기 전용으로 (선택사항)
    readonly_fields = ('number',) 
    # 수정할 필드만 노출
    fields = ('number', 'correct_answer', 'score', 'category')
    # 접기 기능 (목록이 너무 기니까)
    classes = ['collapse']

# 2. 모의고사 정보(MockExamInfo) 관리자 설정
@admin.register(MockExamInfo)
class MockExamInfoAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'grade', 'title', 'created_at')
    list_filter = ('year', 'grade')
    search_fields = ('title',)
    
    # 문항 수정을 위한 인라인 연결
    inlines = [QuestionInline]

# 3. [NEW] 학생 성적 결과(MockExam) 관리자 설정 (이게 중복되었던 부분입니다)
@admin.register(MockExam)
class MockExamAdmin(admin.ModelAdmin):
    # 목록에서 바로 보여줄 컬럼들
    list_display = ('student', 'title', 'score', 'grade', 'exam_date', 'recorded_by')
    
    # 우측 필터 메뉴
    list_filter = ('title', 'grade', 'exam_date')
    
    # 검색창 (학생 이름, 시험 제목)
    search_fields = ('student__name', 'title', 'note')
    
    # 수정 불가능한 읽기 전용 필드
    readonly_fields = ('student_answers', 'wrong_question_numbers', 'recorded_by')

    # 상세 페이지 그룹핑
    fieldsets = (
        ('기본 정보', {
            'fields': ('student', 'title', 'exam_date', 'recorded_by')
        }),
        ('성적 요약', {
            'fields': ('score', 'grade', 'note')
        }),
        ('상세 분석', {
            'fields': ('wrong_listening', 'wrong_vocab', 'wrong_grammar', 'wrong_reading')
        }),
        ('데이터 로그', {
            'fields': ('wrong_question_numbers', 'student_answers'),
            'classes': ('collapse',) # 클릭해야 펼쳐지도록 접어두기
        }),
    )