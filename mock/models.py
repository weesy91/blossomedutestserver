# mock/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import StudentProfile

class MockExam(models.Model):
    """
    모의고사 성적 기록 모델
    """
    # 기본 정보
    student = models.ForeignKey(
        StudentProfile, 
        on_delete=models.CASCADE, 
        related_name='mock_exams',
        verbose_name="학생"
    )
    exam_date = models.DateField(default=timezone.now, verbose_name="시행일")
    title = models.CharField(max_length=50, verbose_name="시험명", help_text="예: 3월 1주차 모의고사, 2024 고1 3월 학평 등")
    
    # 성적 정보
    score = models.IntegerField(verbose_name="원점수")
    grade = models.IntegerField(verbose_name="등급", null=True, blank=True)
    student_answers = models.JSONField(default=dict, verbose_name="학생 마킹 답안")
    # 오답 유형 분석 (틀린 문항 수)
    # 필요에 따라 필드 추가/삭제 가능
    wrong_question_numbers = models.JSONField(default=list, verbose_name="틀린 문항 번호")
    wrong_listening = models.IntegerField(default=0, verbose_name="듣기 오답 수")
    wrong_vocab = models.IntegerField(default=0, verbose_name="어휘 오답 수")
    wrong_grammar = models.IntegerField(default=0, verbose_name="어법 오답 수")
    wrong_reading = models.IntegerField(default=0, verbose_name="독해 오답 수")

    # 관리 정보
    note = models.TextField(blank=True, verbose_name="비고/피드백")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="입력한 선생님"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "모의고사 성적"
        verbose_name_plural = "모의고사 성적"
        ordering = ['-exam_date'] # 최신순 정렬

    def __str__(self):
        return f"[{self.exam_date}] {self.student.name} - {self.score}점"

    @property
    def total_wrong(self):
        """총 틀린 개수 계산"""
        return self.wrong_listening + self.wrong_vocab + self.wrong_grammar + self.wrong_reading
    
class MockExamInfo(models.Model):
    """
    모의고사 회차 정보 (예: 2024년 3월 고1 모의고사)
    """
    GRADE_CHOICES = [
        (1, '고1'), (2, '고2'), (3, '고3')
    ]
    
    title = models.CharField(max_length=100, verbose_name="시험명") # 예: 2024 3월 학평
    year = models.IntegerField(verbose_name="연도", default=timezone.now().year)
    month = models.IntegerField(verbose_name="월")
    grade = models.IntegerField(choices=GRADE_CHOICES, verbose_name="대상 학년")
    
    is_active = models.BooleanField(default=True, verbose_name="활성 상태") # 목록에 표시 여부
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "모의고사 정답지(회차)"
        verbose_name_plural = "모의고사 정답지(회차)"
        ordering = ['-year', '-month', 'grade']

    def __str__(self):
        return f"[{self.year}년 {self.month}월 고{self.grade}] {self.title}"


class MockExamQuestion(models.Model):
    """
    각 회차별 문항 정보 (정답, 배점, 유형)
    """
    # 대한민국 고등영어 표준 유형 분류
    CATEGORY_CHOICES = [
        ('LISTENING', '듣기'),               # 1~17번
        ('PURPOSE', '목적/심경'),            # 18~19번
        ('TOPIC', '주제/제목/요지/주장'),    # 20~24번 (대의파악)
        ('DATA', '도표/안내문/일치'),        # 25~28번 (내용일치)
        ('MEANING', '함축의미추론'),         # 21번 (밑줄 의미)
        ('GRAMMAR', '어법'),                 # 29번
        ('VOCAB', '어휘'),                   # 30번
        ('BLANK', '빈칸추론'),               # 31~34번 (킬러)
        ('FLOW', '무관한 문장'),             # 35번
        ('ORDER', '글의 순서'),              # 36~37번 (킬러)
        ('INSERT', '문장 삽입'),             # 38~39번 (킬러)
        ('SUMMARY', '요약문'),               # 40번
        ('LONG', '장문독해'),                # 41~45번
    ]

    mock_exam = models.ForeignKey(MockExamInfo, on_delete=models.CASCADE, related_name='questions')
    number = models.IntegerField(verbose_name="문항 번호")
    correct_answer = models.IntegerField(verbose_name="정답")
    score = models.IntegerField(default=2, verbose_name="배점")
    
    # max_length를 20으로 늘리고, default를 가장 많은 'TOPIC'이나 'BLANK' 등으로 설정
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='TOPIC', verbose_name="유형")

    class Meta:
        verbose_name = "문항 정답"
        verbose_name_plural = "문항 정답"
        ordering = ['number']
        unique_together = ('mock_exam', 'number')

    def __str__(self):
        return f"{self.number}번 ({self.get_category_display()})"
    
# mock/models.py (기존 코드 아래에 추가)

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=MockExamInfo)
def auto_create_questions(sender, instance, created, **kwargs):
    """
    모의고사 정보(MockExamInfo)가 처음 생성될 때,
    1번부터 45번까지 표준 유형에 맞춰 문항을 자동 생성합니다.
    """
    if created:
        # 대한민국 고등 영어 표준 유형 프리셋 (번호: 유형코드)
        # 매년 조금씩 바뀌지만 대체로 이 틀을 유지합니다.
        preset_map = {
            # 듣기 (1~17)
            **{i: 'LISTENING' for i in range(1, 18)},
            
            # 독해 (18~45)
            18: 'PURPOSE',  # 목적
            19: 'PURPOSE',  # 심경
            20: 'TOPIC',    # 주장
            21: 'MEANING',  # 함축의미
            22: 'TOPIC',    # 요지
            23: 'TOPIC',    # 주제
            24: 'TOPIC',    # 제목
            25: 'DATA',     # 도표
            26: 'DATA',     # 내용일치
            27: 'DATA',     # 안내문
            28: 'DATA',     # 안내문
            29: 'GRAMMAR',  # 어법
            30: 'VOCAB',    # 어휘
            31: 'BLANK',    # 빈칸
            32: 'BLANK',    # 빈칸
            33: 'BLANK',    # 빈칸
            34: 'BLANK',    # 빈칸
            35: 'FLOW',     # 무관한 문장
            36: 'ORDER',    # 순서
            37: 'ORDER',    # 순서
            38: 'INSERT',   # 삽입
            39: 'INSERT',   # 삽입
            40: 'SUMMARY',  # 요약문
            41: 'LONG',     # 장문1
            42: 'LONG',     # 장문1
            43: 'LONG',     # 장문2
            44: 'LONG',     # 장문2
            45: 'LONG',     # 장문2
        }

        questions_to_create = []
        for number in range(1, 46):
            # 기본 배점은 2점으로 설정 (나중에 3점짜리만 수정하면 됨)
            questions_to_create.append(
                MockExamQuestion(
                    mock_exam=instance,
                    number=number,
                    correct_answer=1, # 임시 정답 1 (나중에 수정)
                    score=2,
                    category=preset_map.get(number, 'TOPIC') # 매핑 안된건 기본 TOPIC
                )
            )
        
        # 45개 한방에 DB에 저장 (속도 최적화)
        MockExamQuestion.objects.bulk_create(questions_to_create)