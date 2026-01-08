from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q # [필수] Q 객체 추가
from datetime import datetime, timedelta
import json

from core.models import StudentProfile, ClassTime
from academy.models import TemporarySchedule

# ... (schedule_change 함수 등 위쪽 코드는 기존과 동일하게 유지) ...

@login_required
def schedule_change(request, student_id):
    # (기존 코드 유지)
    student = get_object_or_404(StudentProfile, id=student_id)
    initial_subject = request.GET.get('subject', 'SYNTAX') 

    def generate_slots(start_str, end_str, interval_min):
        slots = []
        current = datetime.strptime(start_str, "%H:%M")
        end = datetime.strptime(end_str, "%H:%M")
        while current <= end:
            slots.append(current.strftime("%H:%M"))
            current += timedelta(minutes=interval_min)
        return slots

    syntax_morning = generate_slots("09:00", "12:20", 40)
    syntax_afternoon = generate_slots("13:20", "20:40", 40)
    full_syntax_slots = syntax_morning + syntax_afternoon
    full_reading_slots = generate_slots("09:00", "20:30", 30)

    weekday_syntax = full_syntax_slots
    weekend_syntax = full_syntax_slots
    weekday_reading = full_reading_slots
    weekend_reading = full_reading_slots

    if request.method == 'POST':
        subject = request.POST.get('subject')
        new_date_str = request.POST.get('new_date')
        new_time_str = request.POST.get('new_time') 
        is_extra = request.POST.get('is_extra') == 'on'
        note = request.POST.get('note', '')

        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time_str, '%H:%M').time()
            
            weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
            day_code = weekday_map[new_date.weekday()]
            
            target_class_obj = ClassTime.objects.filter(
                day=day_code, 
                start_time=new_time,
                name__contains='구문' if subject == 'SYNTAX' else '독해'
            ).first()

            TemporarySchedule.objects.create(
                student=student, 
                subject=subject, 
                new_date=new_date, 
                new_start_time=new_time,
                target_class=target_class_obj,
                is_extra_class=is_extra, 
                note=note
            )
            messages.success(request, f"{student.name} 학생의 {subject} {'보강' if is_extra else '일정 변경'}이 설정되었습니다.")
            return redirect('academy:class_management')
        except ValueError:
            messages.error(request, "날짜 또는 시간 형식이 올바르지 않습니다.")
            return redirect(request.path)

    return render(request, 'academy/schedule_change_form.html', {
        'student': student, 'initial_subject': initial_subject, 'today': timezone.now().date(),
        'weekday_syntax_json': json.dumps(weekday_syntax),
        'weekday_reading_json': json.dumps(weekday_reading),
        'weekend_syntax_json': json.dumps(weekend_syntax),
        'weekend_reading_json': json.dumps(weekend_reading),
    })

# ... (check_availability 함수 등 기존 코드 유지) ...
def check_availability(request):
    """
    [AJAX] 특정 날짜, 특정 선생님의 마감된 시간대(String List)를 반환
    """
    student_id = request.GET.get('student_id')
    subject = request.GET.get('subject')
    date_str = request.GET.get('date')

    if not (student_id and subject and date_str): 
        return JsonResponse({'booked': []})

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        student = StudentProfile.objects.get(id=student_id)
        
        # 구문(SYNTAX)일 때만 1:1 중복 체크 진행 (독해는 중복 허용)
        if subject != 'SYNTAX': 
            return JsonResponse({'booked': []})

        teacher = student.syntax_teacher
        if not teacher: 
            return JsonResponse({'booked': []})

        booked_times = set()
        weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        day_code = weekday_map[target_date.weekday()]
        
        # ------------------------------------------------------------------
        # [1-1] 정규 수업(Regular Class) 중복 체크
        # ------------------------------------------------------------------
        other_syntax_students = StudentProfile.objects.filter(
            syntax_teacher=teacher, 
            syntax_class__day=day_code
        ).exclude(id=student.id).select_related('syntax_class')

        for s in other_syntax_students:
            # 해당 날짜에 보강/변경으로 인해 수업이 '이동'되지 않은 경우만 점유
            if not TemporarySchedule.objects.filter(student=s, original_date=target_date, subject='SYNTAX').exists():
                booked_times.add(s.syntax_class.start_time.strftime('%H:%M'))

        # ------------------------------------------------------------------
        # [1-2] 고정 추가 수업(Fixed Extra Class) 중복 체크 (✅ 추가된 부분)
        # ------------------------------------------------------------------
        # 선생님이 진행하는 '구문' 타입의 추가 수업도 1:1이므로 겹치면 안 됨
        other_extra_students = StudentProfile.objects.filter(
            extra_class_teacher=teacher,
            extra_class_type='SYNTAX', # 구문 타입만 체크
            extra_class__day=day_code
        ).exclude(id=student.id).select_related('extra_class')

        for s in other_extra_students:
            # 추가 수업은 보통 이동이 드물지만, 혹시 모르니 체크 (일단은 무조건 점유로 처리)
            if s.extra_class:
                booked_times.add(s.extra_class.start_time.strftime('%H:%M'))

        # ------------------------------------------------------------------
        # [2] 임시 보강/변경(Temporary Schedule) 중복 체크
        # ------------------------------------------------------------------
        # 해당 날짜에 새로 들어온 스케줄 확인
        temp_schedules = TemporarySchedule.objects.filter(
            new_date=target_date, 
            subject='SYNTAX' # 구문 수업으로 잡힌 것들
        ).select_related('student')

        for ts in temp_schedules:
            # 해당 스케줄의 담당 쌤이 '나(teacher)'인 경우
            # (주의: 임시 스케줄 모델에 teacher 필드가 없다면, 학생의 담당 쌤을 확인)
            ts_teacher = ts.student.syntax_teacher
            
            if ts_teacher == teacher and ts.student.id != student.id:
                if ts.new_start_time:
                    booked_times.add(ts.new_start_time.strftime('%H:%M'))

        return JsonResponse({'booked': sorted(list(booked_times))})
    except Exception as e:
        print(f"Error in check_availability: {e}")
        return JsonResponse({'booked': []})


# 👇 [핵심 수정] 이 함수를 아래 내용으로 완전히 교체하세요!
def get_occupied_times(request):
    """
    특정 선생님의 '구문(1:1)' 수업으로 선점된 시간표 ID 목록을 반환합니다.
    - 정규 구문 수업
    - 보강(추가) 수업 중 '구문' 타입
    """
    teacher_id = request.GET.get('teacher_id')
    # subject 파라미터는 더 이상 'syntax'인지 체크하는 용도로 쓰지 않고, 
    # 무조건 해당 선생님의 1:1(구문) 점유 시간을 반환합니다.
    
    current_student_id = request.GET.get('current_student_id') 

    if not teacher_id:
        return JsonResponse({'occupied_ids': []})

    try:
        # 1. 정규 구문 수업 (Regular Syntax)
        regular_qs = StudentProfile.objects.filter(syntax_teacher_id=teacher_id)
        if current_student_id:
            regular_qs = regular_qs.exclude(id=current_student_id)
        
        regular_ids = list(regular_qs.values_list('syntax_class_id', flat=True))

        # 2. 보강(추가) 수업 중 '구문' 타입 (Extra Class - Syntax)
        # [조건] extra_class_teacher가 이 선생님이고 + 타입이 'SYNTAX'인 경우
        extra_qs = StudentProfile.objects.filter(
            extra_class_teacher_id=teacher_id,
            extra_class_type='SYNTAX'
        )
        if current_student_id:
            extra_qs = extra_qs.exclude(id=current_student_id)
            
        extra_ids = list(extra_qs.values_list('extra_class_id', flat=True))

        # 3. 합치기 (중복 제거 및 None 제거)
        all_ids = set(regular_ids + extra_ids)
        if None in all_ids:
            all_ids.remove(None)

        # 리스트로 변환하여 반환
        return JsonResponse({'occupied_ids': list(all_ids)})

    except Exception as e:
        print(f"Error in get_occupied_times: {e}")
        return JsonResponse({'occupied_ids': []})