# academy/management/commands/check_absences.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import StudentProfile
from academy.models import Attendance
from academy.utils import get_today_class_start_time

class Command(BaseCommand):
    help = '수업 시작 시간이 지났는데 등원하지 않은 학생을 찾아 자동으로 결석 처리합니다.'

    def handle(self, *args, **options):
        # 로그 파일에 찍힐 시간
        now = timezone.now()
        today = now.date()
        
        # 주석: Cron 로그 확인용 (너무 자주 찍히면 주석 처리)
        # self.stdout.write(f"[{now}] 자동 출석 체크 실행 중...")

        # 1. 상태가 'ACTIVE(재원)'인 학생들만 조회
        # (모델에 status 필드가 없다면 .all() 사용)
        students = StudentProfile.objects.all() 

        check_count = 0
        absent_created = 0

        for student in students:
            # 2. 이미 오늘 출석(등원/지각/결석) 기록이 있으면 패스
            if Attendance.objects.filter(student=student, date=today).exists():
                continue

            # 3. 오늘 수업 시작 시간 가져오기 (없으면 패스)
            start_time = get_today_class_start_time(student)
            if start_time is None:
                continue

            # 비교를 위해 datetime 객체로 변환
            class_start_dt = timezone.make_aware(datetime.combine(today, start_time))

            # 4. 현재 시간이 수업 시간보다 지났는지 확인
            if now > class_start_dt:
                diff = now - class_start_dt
                minutes_passed = diff.total_seconds() / 60
                
                # (A) 40분 이상 지났으면 -> '결석(ABSENT)' 확정 처리
                if minutes_passed >= 40:
                    Attendance.objects.create(
                        student=student,
                        date=today,
                        status='ABSENT',
                        memo='시스템 자동 결석 처리 (40분 경과)'
                    )
                    self.stdout.write(self.style.ERROR(f"❌ [결석 처리] {student.name} (수업: {start_time}, {int(minutes_passed)}분 지남)"))
                    absent_created += 1
                
                # (B) 10분 ~ 40분 사이 -> (추후 구현) 부모님께 지각 알림 문자 발송 등
                elif minutes_passed >= 10:
                    # self.stdout.write(self.style.WARNING(f"⚠️ [지각 의심] {student.name} (수업: {start_time}, {int(minutes_passed)}분 지남)"))
                    pass

        if absent_created > 0:
            self.stdout.write(self.style.SUCCESS(f"=== 결과: {absent_created}명 결석 처리 완료 ==="))