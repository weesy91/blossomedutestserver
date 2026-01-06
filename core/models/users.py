from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
import datetime

# 방금 만든 organization 파일에서 조직 정보를 가져옵니다
from .organization import Branch, School, ClassTime

# ==========================================
# 1. 선생님 프로필 (담당 과목 설정용)
# ==========================================
class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    
    # 소속 지점
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="소속 지점")
    name = models.CharField(max_length=20, null=True, blank=True, verbose_name="선생님 성함")

    # 직책 구분
    POSITION_CHOICES = [
        ('TEACHER', '일반 강사'),
        ('VICE', '부원장'),
        ('PRINCIPAL', '원장'),
    ]
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='TEACHER', verbose_name="직책")

    # 부원장일 경우 관리할 선생님들
    managed_teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='managers',
        limit_choices_to={'is_staff': True},
        verbose_name="[부원장용] 담당 강사 선택"
    )

    # 수업 가능 여부
    is_syntax_teacher = models.BooleanField(default=False, verbose_name="구문 수업 가능")
    is_reading_teacher = models.BooleanField(default=False, verbose_name="독해 수업 가능")
    
    def __str__(self):
        roles = []
        if self.is_syntax_teacher: roles.append("구문")
        if self.is_reading_teacher: roles.append("독해")
        role_str = "/".join(roles) if roles else "미정"
        branch_name = self.branch.name if self.branch else "지점미정"
        return f"[{branch_name}] {self.user.username} ({role_str})"

# ==========================================
# 2. 학생 프로필
# ==========================================
class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="소속 지점")

    name = models.CharField(max_length=10, verbose_name="학생 이름")
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="학교")
    
    class GradeChoices(models.IntegerChoices):
        E1=1,'초1'; E2=2,'초2'; E3=3,'초3'; E4=4,'초4'; E5=5,'초5'; E6=6,'초6'
        M1=7,'중1'; M2=8,'중2'; M3=9,'중3'; H1=10,'고1'; H2=11,'고2'; H3=12,'고3'; GRAD=13,'졸업/성인'
    base_year = models.IntegerField(verbose_name="기준 연도", default=datetime.date.today().year)
    base_grade = models.IntegerField(choices=GradeChoices.choices, verbose_name="기준 학년", default=7)

    address = models.CharField(max_length=200, verbose_name="주소", blank=True, null=True)
    attendance_code = models.CharField(max_length=8, null=True, blank=True, verbose_name="출석 코드")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="전화번호")
    parent_phone_mom = models.CharField(max_length=15, verbose_name="어머님 연락처", blank=True, null=True)
    parent_phone_dad = models.CharField(max_length=15, verbose_name="아버님 연락처", blank=True, null=True)
    
    # 구문 담당
    syntax_class = models.ForeignKey(
        ClassTime, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="구문 시간표", related_name="students_syntax",
        limit_choices_to={'name__contains': '구문'} 
    )
    syntax_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="구문 담당 선생님", related_name='syntax_students',
        limit_choices_to={'staff_profile__is_syntax_teacher': True}
    )

    # 독해 담당
    reading_class = models.ForeignKey(
        ClassTime, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="독해 시간표", related_name="students_reading",
        limit_choices_to={'name__contains': '독해'}
    )
    reading_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="독해 담당 선생님", related_name='reading_students',
        limit_choices_to={'staff_profile__is_reading_teacher': True}
    )

    # 추가 수업
    extra_class = models.ForeignKey(
        ClassTime, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="추가 수업 시간", related_name="students_extra"
    )
    extra_class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="추가 수업 담당 선생님", related_name='extra_students'
    )
    extra_class_type = models.CharField(
        max_length=10,
        choices=[('SYNTAX', '구문'), ('READING', '독해')],
        null=True, blank=True,
        verbose_name="추가 수업 종류"
    )

    memo = models.TextField(blank=True, verbose_name="특이사항 메모")
    last_failed_at = models.DateTimeField(null=True, blank=True)
    last_wrong_failed_at = models.DateTimeField(null=True, blank=True)
    
    @property
    def current_grade(self):
        return min(self.base_grade + (timezone.now().year - self.base_year), 13)

    @property
    def extra_class_day(self):
        if self.extra_class: return self.extra_class.day
        return None
        
    @property
    def current_grade_display(self):
        return self.GradeChoices(self.current_grade).label

    def save(self, *args, **kwargs):
        # [수정 2] 휴대폰 번호 뒷 8자리를 가져오도록 로직 변경
        if not self.attendance_code and self.phone_number:
            clean_number = self.phone_number.replace('-', '').strip()
            if len(clean_number) >= 8: 
                self.attendance_code = clean_number[-8:] # 뒤에서 8자리
            else:
                self.attendance_code = clean_number # 번호가 짧으면 그대로 저장
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"[{self.branch.name if self.branch else '지점미정'}] {self.name}"
    
    class Meta:
        verbose_name = "학생 프로필"
        verbose_name_plural = "학생 프로필"

# ==========================================
# 3. 계정 관리 (Proxy Models)
# ==========================================
class StaffUser(User):
    class Meta:
        proxy = True 
        app_label = 'auth'
        verbose_name = "선생님 계정"
        verbose_name_plural = "선생님 계정 관리"

class StudentUser(User):
    class Meta:
        proxy = True 
        app_label = 'auth'
        verbose_name = "학생 계정"
        verbose_name_plural = "학생 계정 관리"