from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from core.models import StudentProfile, ClassTime # ClassTime 임포트 확인
from academy.models import TemporarySchedule

@login_required
def schedule_change(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    initial_subject = request.GET.get('subject', 'SYNTAX') 

    # 1. 시간 슬롯 생성 헬퍼 함수
    def generate_slots(start_str, end_str, interval_min):
        slots = []
        current = datetime.strptime(start_str, "%H:%M")
        end = datetime.strptime(end_str, "%H:%M") # 이 시간 '이전'까지만 생성 (end 포함하려면 로직 조정 필요)
        
        # end_str 시간에 딱 시작하는 수업까지 포함하고 싶으면 <= 사용
        # 여기서는 안전하게 end 시간 "이전"에 시작하는 것들만 담습니다.
        while current <= end:
            slots.append(current.strftime("%H:%M"))
            current += timedelta(minutes=interval_min)
        return slots

    # =========================================================
    # [수정된 로직] 
    # 1. 구문 (Syntax): 40분 간격
    #    - 오전: 09:00 ~ 12:20 (12:20 시작이 막타임)
    #    - 오후: 13:20 ~ 20:40 (20:40 시작이 막타임)
    # =========================================================
    syntax_morning = generate_slots("09:00", "12:20", 40)
    syntax_afternoon = generate_slots("13:20", "20:40", 40)
    full_syntax_slots = syntax_morning + syntax_afternoon

    # =========================================================
    # [수정된 로직]
    # 2. 독해 (Reading): 30분 간격
    #    - 전체: 09:00 ~ 20:30 (20:30 시작이 막타임)
    # =========================================================
    full_reading_slots = generate_slots("09:00", "20:30", 30)

    # ---------------------------------------------------------
    # [중요] 기존 JS 코드와의 호환성을 위해 변수명은 유지하되,
    # 내용은 위에서 만든 '새 규칙'으로 덮어씌웁니다.
    # (평일/주말 구분 없이 학원 규칙이 통일되었다면 이렇게 하는 게 확실합니다)
    # ---------------------------------------------------------
    weekday_syntax = full_syntax_slots
    weekend_syntax = full_syntax_slots # 주말도 동일하게 적용
    
    weekday_reading = full_reading_slots
    weekend_reading = full_reading_slots # 주말도 동일하게 적용


    if request.method == 'POST':
        subject = request.POST.get('subject')
        new_date_str = request.POST.get('new_date')
        new_time_str = request.POST.get('new_time') 
        is_extra = request.POST.get('is_extra') == 'on'
        note = request.POST.get('note', '')

        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time_str, '%H:%M').time()
            
            # [추가] 선택한 시간과 일치하는 ClassTime 객체 찾기 (DB 연결)
            # 폼에서는 시간(Text)만 넘어오므로, DB에서 해당 요일/시간의 객체를 찾아 연결해주는 것이 좋습니다.
            weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
            day_code = weekday_map[new_date.weekday()]
            
            # 이름에 '구문' 혹은 '독해'가 포함된 시간표 중 매칭되는 것 검색
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
                target_class=target_class_obj, # [중요] DB 객체 연결 (없으면 None)
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

# 아래 함수들은 기존 그대로 유지 (변경 없음)
def check_availability(request):
    student_id = request.GET.get('student_id')
    subject = request.GET.get('subject')
    date_str = request.GET.get('date')

    if not (student_id and subject and date_str): 
        return JsonResponse({'booked': []})

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        student = StudentProfile.objects.get(id=student_id)
        
        # 구문(SYNTAX)일 때만 1:1 중복 체크 진행
        if subject != 'SYNTAX': 
            return JsonResponse({'booked': []})

        teacher = student.syntax_teacher
        if not teacher: 
            return JsonResponse({'booked': []})

        booked_times = set()
        weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        day_code = weekday_map[target_date.weekday()]
        
        # [1] 정규 수업 중복 체크: 해당 선생님의 다른 구문 학생들 조사
        other_syntax_students = StudentProfile.objects.filter(
            syntax_teacher=teacher, 
            syntax_class__day=day_code
        ).exclude(id=student.id).select_related('syntax_class')

        for s in other_syntax_students:
            # 해당 날짜에 보강으로 인해 정규 수업이 '이동(취소)'되지 않은 경우만 추가
            if not TemporarySchedule.objects.filter(student=s, original_date=target_date, subject='SYNTAX').exists():
                booked_times.add(s.syntax_class.start_time.strftime('%H:%M'))

        # [2] 보강 스케줄 중복 체크: 해당 날짜에 이미 잡힌 선생님의 다른 구문 보강
        temp_schedules = TemporarySchedule.objects.filter(
            new_date=target_date, 
            subject='SYNTAX'
        ).select_related('student')

        for ts in temp_schedules:
            if ts.student.syntax_teacher == teacher and ts.student.id != student.id:
                if ts.new_start_time:
                    booked_times.add(ts.new_start_time.strftime('%H:%M'))

        return JsonResponse({'booked': sorted(list(booked_times))})
    except Exception as e:
        return JsonResponse({'booked': []})

def get_occupied_times(request):
    teacher_id = request.GET.get('teacher_id')
    subject = request.GET.get('subject')
    current_student_id = request.GET.get('current_student_id') 

    if not teacher_id or subject != 'syntax': # 구문만 1:1 체크
        return JsonResponse({'occupied_ids': []})

    try:
        # 이 선생님의 다른 구문 학생들을 찾음
        occupied_qs = StudentProfile.objects.filter(syntax_teacher_id=teacher_id)
        
        if current_student_id:
            occupied_qs = occupied_qs.exclude(id=current_student_id)

        # 배정된 ClassTime의 ID 리스트 반환
        occupied_ids = list(occupied_qs.values_list('syntax_class_id', flat=True))
        # None(미지정) 값 제거
        occupied_ids = [i for i in occupied_ids if i is not None]

        return JsonResponse({'occupied_ids': occupied_ids})
    except Exception:
        return JsonResponse({'occupied_ids': []})