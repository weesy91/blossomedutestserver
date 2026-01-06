# reports/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class MonthlyReport(models.Model):
    # 1. 기본 정보 (누구의, 언제 성적표인가?)
    student = models.ForeignKey('core.StudentProfile', on_delete=models.CASCADE, related_name='reports', verbose_name="학생")
    year = models.IntegerField(verbose_name="연도", default=timezone.now().year)
    month = models.IntegerField(verbose_name="월", default=timezone.now().month)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # [핵심] 로그인 없이 접근하기 위한 비밀 코드 (예: a1b2-c3d4...)
    # url에 /reports/view/a1b2-c3d4/ 이렇게 쓰일 예정
    access_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # ==========================================
    # Part 1. 출결 및 태도 (Attendance)
    # ==========================================
    total_days = models.IntegerField(default=0, verbose_name="총 수업 일수")
    present_days = models.IntegerField(default=0, verbose_name="출석 횟수")
    late_days = models.IntegerField(default=0, verbose_name="지각 횟수")
    absent_days = models.IntegerField(default=0, verbose_name="결석 횟수")
    
    # 보강 관련
    makeup_count = models.IntegerField(default=0, verbose_name="보강 횟수")
    unexcused_absent = models.IntegerField(default=0, verbose_name="무단 결석")

    # ==========================================
    # Part 2. 어휘 (Vocab) - Vocab 앱 데이터 스냅샷
    # ==========================================
    vocab_progress_info = models.CharField(max_length=100, blank=True, verbose_name="단어장 진행 현황") # 예: "Day 11 ~ Day 20"
    vocab_test_count = models.IntegerField(default=0, verbose_name="총 응시 횟수")
    vocab_pass_count = models.IntegerField(default=0, verbose_name="Pass 횟수")
    vocab_fail_count = models.IntegerField(default=0, verbose_name="Fail 횟수")
    
    # 그래프를 그리기 위한 데이터를 텍스트(JSON 형태)로 저장해둘 수도 있음
    # 일단은 평균 점수만 저장
    vocab_average_score = models.FloatField(default=0.0, verbose_name="단어 시험 평균 점수")

    # ==========================================
    # Part 3. 구문 및 독해 수업 (Class Logs)
    # ==========================================
    # 선생님이 작성한 수업 일지 내용을 요약해서 저장하거나, 긴 텍스트로 저장
    study_summary = models.TextField(blank=True, verbose_name="수업 진행 내용 요약")
    textbook_progress = models.CharField(max_length=200, blank=True, verbose_name="교재 진행 상황")
    performance_comment = models.TextField(blank=True, verbose_name="수업 수행도 코멘트")

    # ==========================================
    # Part 4. 월말 평가 (Monthly Exam) -> 레이더 차트용
    # ==========================================
    exam_score_vocab = models.IntegerField(default=0, verbose_name="[월말] 어휘 점수")
    exam_score_syntax = models.IntegerField(default=0, verbose_name="[월말] 구문 점수")
    exam_score_reading = models.IntegerField(default=0, verbose_name="[월말] 독해 점수")
    exam_score_listening = models.IntegerField(default=0, verbose_name="[월말] 듣기 점수") # 필요시 사용
    
    # 비교 분석 데이터 (반 평균 등)
    class_average_score = models.FloatField(default=0.0, verbose_name="반 평균")
    
    # 선생님의 종합 코멘트 (가장 상단에 뜰 편지)
    overall_comment = models.TextField(blank=True, verbose_name="선생님 총평")

    def __str__(self):
        return f"{self.year}년 {self.month}월 - {self.student.name}"

    class Meta:
        verbose_name = "월간 성적표"
        verbose_name_plural = "월간 성적표"
        # 한 학생은 한 달에 하나의 성적표만 가짐
        unique_together = ('student', 'year', 'month')