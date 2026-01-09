from django.shortcuts import render
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from datetime import datetime, timedelta
from academy.models import Attendance
from core.models import StudentProfile
from academy.utils import get_today_class_start_time

# from utils.aligo import send_alimtalk  <-- 아직 파일 없으면 주석 유지

@user_passes_test(lambda u: u.is_superuser, login_url='core:teacher_home')
def attendance_kiosk(request):
    """
    키오스크 출석 체크 함수
    """
    if request.method == 'POST':
        raw_code = request.POST.get('attendance_code', '')
        code = raw_code.strip()
        
        profiles = StudentProfile.objects.filter(attendance_code=code)

        if not profiles.exists():
            messages.error(request, '등록되지 않은 번호입니다.')
            return render(request, 'academy/kiosk.html')
        
        profile = profiles.first()
        today = timezone.now().date()
        now = timezone.now()
        
        # 이미 출석했는지 확인
        if Attendance.objects.filter(student=profile, date=today).exists():
            log = Attendance.objects.filter(student=profile, date=today).first()
            messages.info(request, f"{profile.name} 학생, 이미 등원 처리되어 있습니다. ({log.get_status_display()})")
            return render(request, 'academy/kiosk.html', {'status': log.status})

        # 시간 판별
        earliest_start = get_today_class_start_time(profile)
        status = 'PRESENT'
        msg_text = ""
        
        if earliest_start is None:
            status = 'PRESENT'
            msg_text = f"{profile.name} 학생 등원했습니다. (수업 없음)"
        else:
            # 타임존 비교 에러 방지 코드 적용
            class_start_dt = datetime.combine(today, earliest_start)
            if timezone.is_aware(now):
                class_start_dt = timezone.make_aware(class_start_dt)
            
            limit_time = class_start_dt + timedelta(minutes=40)

            if now < class_start_dt:
                status = 'PRESENT'
            elif now <= limit_time:
                status = 'LATE'
            else:
                status = 'ABSENT'
                
            if status == 'PRESENT':
                msg_text = f"{profile.name} 학생 등원했습니다. (정상 출석)"
            elif status == 'LATE':
                msg_text = f"{profile.name} 학생 등원했습니다. (지각 처리됨)"
            else:
                msg_text = f"{profile.name} 학생 등원했습니다. (수업 시간 40분 초과 - 결석 처리)"

        Attendance.objects.create(
            student=profile, 
            date=today, 
            check_in_time=now, 
            status=status
        )
        
        messages.success(request, msg_text)
        return render(request, 'academy/kiosk.html', {'status': status})

    return render(request, 'academy/kiosk.html')