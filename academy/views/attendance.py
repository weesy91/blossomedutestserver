from django.shortcuts import render
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from academy.models import Attendance
from core.models import StudentProfile
from academy.utils import get_today_class_start_time

def attendance_kiosk(request):
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
        
        # [수정] student=profile 로 변경
        if Attendance.objects.filter(student=profile, date=today).exists():
            log = Attendance.objects.filter(student=profile, date=today).first()
            messages.info(request, f"{profile.name} 학생, 이미 등원 처리되어 있습니다. ({log.get_status_display()})")
            return render(request, 'academy/kiosk.html', {'status': log.status})

        # 시간 판별 로직
        earliest_start = get_today_class_start_time(profile)
        status = 'PRESENT'
        msg_text = ""
        
        if earliest_start is None:
            status = 'PRESENT'
            msg_text = f"{profile.name} 학생 등원했습니다. (수업 없음)"
        else:
            class_start_datetime = datetime.combine(today, earliest_start)
            if timezone.is_aware(now):
                class_start_datetime = timezone.make_aware(class_start_datetime)
            
            limit_time = class_start_datetime + timedelta(minutes=40)

            if now < class_start_datetime:
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

        # [수정] student=profile 로 변경
        Attendance.objects.create(
            student=profile, 
            date=today, 
            check_in_time=now, 
            status=status
        )
        
        if status == 'PRESENT':
            messages.success(request, msg_text)
        elif status == 'LATE':
            messages.warning(request, msg_text)
        else:
            messages.error(request, msg_text)

        return render(request, 'academy/kiosk.html', {'status': status})

    return render(request, 'academy/kiosk.html')