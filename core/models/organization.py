from django.db import models

# ==========================================
# 1. 지점(캠퍼스) 관리
# ==========================================
class Branch(models.Model):
    name = models.CharField(max_length=20, verbose_name="지점명")
    def __str__(self): return self.name
    class Meta:
        verbose_name = "지점(캠퍼스)"
        verbose_name_plural = "지점(캠퍼스)"

# ==========================================
# 2. 학교 관리
# ==========================================
class School(models.Model):
    branches = models.ManyToManyField(Branch, related_name='schools', verbose_name="관련 지점", blank=True)
    name = models.CharField(max_length=30, verbose_name="학교명")
    region = models.CharField(max_length=30, verbose_name="지역", blank=True)
    def __str__(self): return self.name
    class Meta:
        verbose_name = "학교"
        verbose_name_plural = "학교"

# ==========================================
# 3. 수업 시간표
# ==========================================
class ClassTime(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name="지점", null=True, blank=True)
    name = models.CharField(max_length=50, verbose_name="수업명 (예: 구문_평일)")
    
    class DayChoices(models.TextChoices):
        MON = 'Mon', '월요일'
        TUE = 'Tue', '화요일'
        WED = 'Wed', '수요일'
        THU = 'Thu', '목요일'
        FRI = 'Fri', '금요일'
        SAT = 'Sat', '토요일'
        SUN = 'Sun', '일요일'
    day = models.CharField(max_length=3, choices=DayChoices.choices, verbose_name="요일")
    start_time = models.TimeField(verbose_name="시작 시간")
    end_time = models.TimeField(verbose_name="종료 시간")

    def __str__(self):
        # 날짜 포맷: 시:분 (예: 16:00)
        start_str = self.start_time.strftime('%H:%M')
        # 출력 예시: [월요일] 16:00 (구문)
        return f"[{self.get_day_display()}] {start_str} ({self.name})"

    class Meta:
        verbose_name = "수업 시간표"
        verbose_name_plural = "수업 시간표"