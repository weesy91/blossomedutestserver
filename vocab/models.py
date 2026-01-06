import csv
from io import TextIOWrapper
from django.db import models
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

# ==========================================
# [1] 단어장 관리 (WordBook & Word)
# ==========================================

class Publisher(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="출판사명")

    def __str__(self):
        return self.name

class WordBook(models.Model):
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="출판사")
    title = models.CharField(max_length=100, verbose_name="단어장 제목")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="등록자")
    created_at = models.DateTimeField(auto_now_add=True)
    csv_file = models.FileField(upload_to='csvs/', blank=True, null=True, verbose_name="CSV 파일")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "단어장"
        verbose_name_plural = "단어장"

    # [핵심] CSV 파일 자동 등록 로직
    @transaction.atomic
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.csv_file or self.words.exists():
            return
        
        print(f"--- [DEBUG] 단어장 '{self.title}' 파일 분석 시작 ---")
        file_obj = self.csv_file.file
        file_obj.seek(0)
        
        # 인코딩 처리 (utf-8-sig 또는 cp949)
        try:
            decoded_file = TextIOWrapper(file_obj, encoding='utf-8-sig')
            reader = csv.reader(decoded_file)
            rows = list(reader)
        except UnicodeDecodeError:
            file_obj.seek(0)
            decoded_file = TextIOWrapper(file_obj, encoding='cp949')
            reader = csv.reader(decoded_file)
            rows = list(reader)

        unique_words = {}
        for i, row in enumerate(rows):
            if i == 0 or len(row) < 3: continue # 헤더거나 데이터 부족하면 패스
            
            day_str = row[0].strip()
            eng_val = row[1].strip()
            kor_val = row[2].strip()
            example_val = row[3].strip() if len(row) > 3 else ""
            
            if not eng_val or not kor_val: continue
            if eng_val.lower() in ['word', 'english', '영어']: continue 
            
            try: num_val = int(day_str)
            except ValueError: num_val = 1 

            unique_words[eng_val] = Word(
                book=self, 
                english=eng_val, 
                korean=kor_val, 
                number=num_val, 
                example_sentence=example_val
            )

        if unique_words:
            Word.objects.bulk_create(unique_words.values())
            print(f"--- [성공] {len(unique_words)}개 단어 등록 완료 ---")

class Word(models.Model):
    book = models.ForeignKey(WordBook, on_delete=models.CASCADE, related_name='words')
    number = models.IntegerField(default=1, verbose_name="Day/Unit")
    english = models.CharField(max_length=100)
    korean = models.CharField(max_length=100)
    example_sentence = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('book', 'english')
        ordering = ['number', 'id']

    def __str__(self):
        return f"{self.english} ({self.korean})"


# ==========================================
# [2] 시험 결과 관리 (Test Result)
# ==========================================

# 2-1. 도전 모드 결과 (일반 시험)
class TestResult(models.Model):
    student = models.ForeignKey(
        'core.StudentProfile', 
        on_delete=models.CASCADE, 
        related_name='test_results',
        verbose_name="학생"
    )
    book = models.ForeignKey(WordBook, on_delete=models.CASCADE, verbose_name="시험 본 책")
    score = models.IntegerField(default=0, verbose_name="점수")
    total_count = models.IntegerField(default=30)
    wrong_count = models.IntegerField(default=0)
    test_range = models.CharField(max_length=50, blank=True, verbose_name="시험 범위")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="응시 일시")
    
    class Meta:
        verbose_name = "도전모드 결과"
        verbose_name_plural = "도전모드 결과"

    def __str__(self):
        # self.student.profile.name -> self.student.name 으로 단축됨
        return f"[{self.created_at.date()}] {self.student.name} - {self.score}점"

class TestResultDetail(models.Model):
    result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name='details')
    word_question = models.CharField(max_length=100)
    student_answer = models.CharField(max_length=100)
    correct_answer = models.CharField(max_length=100)
    is_correct = models.BooleanField(default=False)
    is_correction_requested = models.BooleanField(default=False, verbose_name="정답 정정 요청")
    is_resolved = models.BooleanField(default=False, verbose_name="처리 완료")

    def __str__(self):
        return f"{self.word_question} ({'O' if self.is_correct else 'X'})"


# 2-2. 월말 평가 결과
class MonthlyTestResult(models.Model):
    student = models.ForeignKey(
        'core.StudentProfile', 
        on_delete=models.CASCADE, 
        related_name='monthly_results'
    )
    book = models.ForeignKey(WordBook, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=100)
    test_range = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "월말평가 결과"
        verbose_name_plural = "월말평가 결과"

class MonthlyTestResultDetail(models.Model):
    result = models.ForeignKey(MonthlyTestResult, on_delete=models.CASCADE, related_name='details')
    word_question = models.CharField(max_length=100)
    student_answer = models.CharField(max_length=100)
    correct_answer = models.CharField(max_length=100)
    is_correct = models.BooleanField(default=False)
    is_correction_requested = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)


# ==========================================
# [3] 자동 채점 로직 (Signal)
# ==========================================
# 정답 정정 요청을 선생님이 수락(is_correct=True로 변경)하면, 점수도 자동으로 오르게 합니다.

@receiver(post_save, sender=TestResultDetail)
def update_score_on_change(sender, instance, **kwargs):
    result = instance.result
    # 현재 맞은 개수 다시 세기
    real_score = result.details.filter(is_correct=True).count()
    result.score = real_score
    result.wrong_count = result.total_count - real_score
    result.save()


# ==========================================
# [4] 기록 제거시 5분 쿨타임 제거
# ==========================================
@receiver(post_delete, sender=TestResult)
def auto_reset_cooldown(sender, instance, **kwargs):
    # instance.student가 이제 바로 Profile 객체입니다.
    profile = instance.student 
    
    # 더 이상 hasattr 체크나 profile 접근이 필요 없습니다.
    # if not hasattr(student, 'profile'): return (삭제)
    
    now = timezone.now()
    five_mins_ago = now - timedelta(minutes=5)

    # 쿼리 시 student=profile 로 변경
    recent_challenge_fails = TestResult.objects.filter(
        student=profile,
        score__lt=27,
        created_at__gte=five_mins_ago
    ).exclude(test_range="오답집중")

    if not recent_challenge_fails.exists():
        profile.last_failed_at = None

    recent_wrong_fails = TestResult.objects.filter(
        student=profile,
        score__lt=27,
        created_at__gte=five_mins_ago,
        test_range="오답집중"
    )

    if not recent_wrong_fails.exists():
        profile.last_wrong_failed_at = None

    profile.save()

class PersonalWrongWord(models.Model):
    """
    학생이 직접 검색해서 오답 노트에 추가한 단어
    """
    student = models.ForeignKey('core.StudentProfile', on_delete=models.CASCADE, related_name='personal_wrong_words')
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "학생 추가 오답"
        verbose_name_plural = "학생 추가 오답"
        unique_together = ('student', 'word') # 중복 추가 방지

    def __str__(self):
        return f"{self.student.name} - {self.word.english}"
    
class RankingEvent(models.Model):
    title = models.CharField(max_length=100, verbose_name="이벤트 타이틀", help_text="예: 🌞 여름방학 능률보카 격파왕")
    target_book = models.ForeignKey(WordBook, on_delete=models.CASCADE, verbose_name="이벤트 대상 단어장")
    start_date = models.DateField(verbose_name="시작일")
    end_date = models.DateField(verbose_name="종료일")
    is_active = models.BooleanField(default=True, verbose_name="현재 진행 중")

    class Meta:
        verbose_name = "🏆 랭킹 이벤트 설정"
        verbose_name_plural = "🏆 랭킹 이벤트 설정"

    def __str__(self):
        return f"{self.title} ({self.target_book.title})"