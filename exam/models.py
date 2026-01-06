from django.db import models
from django.conf import settings
from academy.models import Textbook

class Question(models.Model):
    category = models.CharField(max_length=20, choices=[('READING', '독해'), ('SYNTAX', '구문')])
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE)
    chapter = models.IntegerField()
    number = models.IntegerField()
    image = models.ImageField(upload_to='questions/')
    answer_image = models.ImageField(upload_to='answers/', blank=True, null=True)
    
    # 문제 스타일
    style = models.CharField(max_length=20, choices=[('CONCEPT', '지문'), ('ANALYSIS', '구문/분석')], default='CONCEPT')
    
    # [중요] 독해 문제 유형 (프린트 시 Logic Check 박스 내용 결정)
    # TOPIC(대의파악), LOGIC(순서/삽입), BLANK(빈칸), DETAIL(일치), STRUCT(구조)
    reading_type = models.CharField(max_length=20, blank=True, null=True)
    question_text = models.TextField(blank=True, verbose_name="지문 텍스트(검색용)")

    def __str__(self):
        return f"{self.textbook.title} - {self.chapter}강 {self.number}번"

class TestPaper(models.Model):
    student = models.ForeignKey('core.StudentProfile', on_delete=models.CASCADE, related_name='test_papers')
    title = models.CharField(max_length=100)
    questions = models.ManyToManyField(Question)
    created_at = models.DateTimeField(auto_now_add=True)
    target_chapters = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.title

class ExamResult(models.Model):
    student = models.ForeignKey('core.StudentProfile', on_delete=models.CASCADE, related_name='exam_results')
    paper = models.ForeignKey(TestPaper, on_delete=models.CASCADE, related_name='results')
    score = models.IntegerField(default=0, verbose_name="점수")
    date = models.DateField(auto_now_add=True, verbose_name="응시일")
    # 하위 호환을 위해 남겨두지만, 실제 데이터는 ExamResultDetail에 저장 권장
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "월말평가 결과"
        verbose_name_plural = "월말평가 결과"

# [NEW] 통계 처리를 위한 상세 결과 테이블
class ExamResultDetail(models.Model):
    result = models.ForeignKey(ExamResult, on_delete=models.CASCADE, related_name='detail_set')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=100, blank=True)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.result.student.name} - {self.question.id} ({'O' if self.is_correct else 'X'})"
    
class QuestionUpload(Question):
    """
    [Admin 메뉴용 가짜 모델]
    이 모델은 실제 DB 테이블을 만들지 않고(proxy=True),
    Admin 페이지에서 '문제 대량 업로드' 메뉴를 보여주기 위한 용도입니다.
    """
    class Meta:
        proxy = True
        verbose_name = '📸 문제 대량 업로드'
        verbose_name_plural = '📸 문제 대량 업로드'