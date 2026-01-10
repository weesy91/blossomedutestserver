from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, time, timedelta
import json
import re
from vocab.models import TestResult
from utils.aligo import send_alimtalk
from academy.models import TemporarySchedule, Textbook, ClassLog, ClassLogEntry, Attendance
from vocab.models import WordBook
from core.models import StudentProfile
from django.contrib.auth.decorators import login_required

# ==========================================
# 1. 수업 목록 조회 (요구사항 1번 충족)
# ==========================================
@login_required
def class_management(request):
    """
    [수업 일지 목록]
    - 지점(Branch) 및 담당 과목(Teacher) 필터링 적용
    - 날짜 이동 기능(prev/next) 복구
    """
    user = request.user
    
    # 1. 로그인 유저의 지점(Branch) 확인
    try:
        staff_profile = getattr(user, 'staff_profile', None)
        staff_branch = staff_profile.branch if staff_profile else None
    except Exception:
        staff_branch = None

    if not staff_branch:
        return render(request, 'academy/class_management.html', {
            'class_list': [], 
            'error': '지점 정보가 없는 계정입니다.'
        })

    date_str = request.GET.get('date')
    search_query = request.GET.get('q', '').strip()
    
    # [수정] 여기가 빠져 있었습니다! 화면에서 화살표를 눌렀을 때 'prev'인지 'next'인지 받아오는 코드
    action = request.GET.get('action') 

    # 2. 날짜 설정
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    # 3. 날짜 이동 로직 (화살표 버튼 대응)
    if action == 'prev':
        target_date -= timedelta(days=1)
        # URL을 깔끔하게 유지하기 위해 계산된 날짜로 리다이렉트
        return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")
    elif action == 'next':
        target_date += timedelta(days=1)
        return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

    target_day_code = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}[target_date.weekday()]

    class_list = []

    # 4. 보강 스케줄 조회
    temp_qs = TemporarySchedule.objects.filter(
        new_date=target_date,
        student__branch=staff_branch
    ).select_related('student')

    if search_query:
        temp_qs = temp_qs.filter(student__name__icontains=search_query)

    for schedule in temp_qs:
        student = schedule.student
        
        # 담당 과목 확인
        is_my_class = False
        if schedule.subject == 'SYNTAX' and student.syntax_teacher == user:
            is_my_class = True
        elif schedule.subject == 'READING' and student.reading_teacher == user:
            is_my_class = True
        elif schedule.subject == 'EXTRA' and student.extra_class_teacher == user:
            is_my_class = True

        if is_my_class:
            attendance = Attendance.objects.filter(student=student, date=target_date).first()
            log = ClassLog.objects.filter(student=student, date=target_date, subject=schedule.subject).first()
            
            class_list.append({
                'student': student,
                'subject': schedule.subject,
                'class_time': schedule.target_class,
                'start_time': schedule.new_start_time,
                'status': '작성완료' if log else '미작성',
                'is_extra': schedule.is_extra_class,
                'note': schedule.note,
                'schedule_id': schedule.id,
                'has_attended': attendance is not None,
                'attendance_status': attendance.status if attendance else 'NONE',
            })
    
    # 5. 정규 수업 조회
    student_qs = StudentProfile.objects.filter(
        branch=staff_branch,
        user__is_active=True 
    ).filter(
        Q(syntax_teacher=user) | Q(reading_teacher=user) | Q(extra_class_teacher=user)
    ).select_related('syntax_class', 'reading_class', 'extra_class')
    
    if search_query:
        student_qs = student_qs.filter(name__icontains=search_query)

    for student in student_qs:
        attendance = Attendance.objects.filter(student=student, date=target_date).first()
        
        item_base = {
            'student': student, 
            'is_extra': False, 
            'note': '',
            'schedule_id': 0, 
            'has_attended': attendance is not None, 
            'attendance_status': attendance.status if attendance else 'NONE',
        }

        # [구문]
        if student.syntax_teacher == user and student.syntax_class and student.syntax_class.day == target_day_code:
            if not TemporarySchedule.objects.filter(student=student, original_date=target_date, subject='SYNTAX').exists():
                log = ClassLog.objects.filter(student=student, date=target_date, subject='SYNTAX').first()
                item = item_base.copy()
                item.update({
                    'subject': 'SYNTAX', 
                    'class_time': student.syntax_class, 
                    'start_time': student.syntax_class.start_time,
                    'status': '작성완료' if log else '미작성'
                })
                class_list.append(item)
        
        # [독해]
        if student.reading_teacher == user and student.reading_class and student.reading_class.day == target_day_code:
            if not TemporarySchedule.objects.filter(student=student, original_date=target_date, subject='READING').exists():
                log = ClassLog.objects.filter(student=student, date=target_date, subject='READING').first()
                item = item_base.copy()
                item.update({
                    'subject': 'READING', 
                    'class_time': student.reading_class, 
                    'start_time': student.reading_class.start_time,
                    'status': '작성완료' if log else '미작성'
                })
                class_list.append(item)

    # 정렬
    class_list.sort(key=lambda x: x['start_time'] if x['start_time'] else time(23, 59))

    return render(request, 'academy/class_management.html', {
        'target_date': target_date, 
        'class_list': class_list,
        'search_query': search_query
    })

@login_required
def create_class_log(request, schedule_id):
    subject = request.GET.get('subject', '')
    student = None
    target_date = None
    
    # 1. 학생 및 날짜 정보 확인
    if schedule_id == 0:
        student_id = request.GET.get('student_id')
        date_str = request.GET.get('date')
        if student_id:
            student = get_object_or_404(StudentProfile, id=student_id)
            if date_str:
                try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError: target_date = timezone.now().date()
            else:
                target_date = timezone.now().date()
    else:
        schedule = get_object_or_404(TemporarySchedule, id=schedule_id)
        student = schedule.student 
        target_date = schedule.new_date
        if not subject: subject = schedule.subject

    if not student:
        messages.error(request, "학생 정보가 없습니다.")
        return redirect('academy:class_management')

    # ==========================================================================
    # [권한 체크] 읽기 전용 모드 판별 (핵심 로직)
    # ==========================================================================
    user = request.user
    
    # 1. 일단 내 학생인지 체크 (아예 남이면 접근 불가)
    is_my_student = (
        student.syntax_teacher == user or 
        student.reading_teacher == user or 
        student.extra_class_teacher == user
    )
    
    # 원장/부원장이면 프리패스
    is_admin = user.is_superuser or (hasattr(user, 'staff_profile') and user.staff_profile.position in ['PRINCIPAL', 'VICE'])
    
    if not (is_my_student or is_admin):
        messages.error(request, "담당 학생이 아닙니다.")
        return redirect('academy:class_management')

    # 2. 수정 권한(Editable) 체크
    can_edit = False
    
    if is_admin:
        can_edit = True
    elif subject == 'SYNTAX' and student.syntax_teacher == user:
        can_edit = True
    elif subject == 'READING' and student.reading_teacher == user:
        can_edit = True
    elif subject == 'EXTRA' and student.extra_class_teacher == user:
        can_edit = True
        
    is_readonly = not can_edit
    

    # ------------------------------------------------------------------
    # [수정] 이전 로그 조회 로직 강화
    # ------------------------------------------------------------------
    
    # 1) 교차 로그 (상대방 선생님 수업 정보) - 기존 기능
    prev_log = None
    if subject == 'SYNTAX':
        prev_log = ClassLog.objects.filter(student=student, subject='READING', date__lt=target_date).order_by('-date').first()
    elif subject == 'READING':
        prev_log = ClassLog.objects.filter(student=student, subject='SYNTAX', date__lt=target_date).order_by('-date').first()

    # 2) [NEW] 나의 지난 로그 (내가 내준 숙제 확인용)
    my_prev_log = ClassLog.objects.filter(
        student=student, 
        subject=subject, # 현재 과목과 동일한 과목 조회
        date__lt=target_date
    ).order_by('-date').first()

    # ------------------------------------------------------------------

    # 3. 교재 목록 준비
    wb_condition = Q(uploaded_by__is_staff=True) | Q(uploaded_by__is_superuser=True)
    
    # 2) 학생 본인의 단어장 추가 (student.user가 존재하는 경우)
    if hasattr(student, 'user') and student.user:
        wb_condition |= Q(uploaded_by=student.user)

    # 필터링 적용
    vocab_books = WordBook.objects.select_related('publisher').filter(wb_condition)
    # [수정 끝]

    vocab_publishers = sorted(set(b.publisher.name for b in vocab_books if b.publisher))
    vocab_books_dict = {
        p: [{'id': b.id, 'title': b.title} for b in vocab_books if b.publisher and b.publisher.name == p]
        for p in vocab_publishers
    }

    syntax_books = Textbook.objects.filter(category='SYNTAX')
    reading_books = Textbook.objects.filter(category='READING')
    grammar_books = Textbook.objects.filter(category='GRAMMAR')
    school_exam_books = Textbook.objects.filter(category='SCHOOL_EXAM')

    # --- POST 요청 처리 ---
    if request.method == 'POST':
        class_log, created = ClassLog.objects.get_or_create(
            student=student, date=target_date, subject=subject,
            defaults={'teacher': request.user, 'comment': request.POST.get('comment', '')}
        )
        
        if not created:
            class_log.teacher = request.user
            class_log.comment = request.POST.get('comment', '')
            class_log.entries.all().delete()

        # 독해 테스트 결과 저장
        if subject == 'READING':
            class_log.reading_test_type = request.POST.get('reading_test_type', '')
            class_log.reading_test_score = request.POST.get('reading_test_score', '')
        else:
            # 구문 단어 테스트 저장
            range_pattern = re.compile(r'^\d+(-\d+)?$')
            v_ids = request.POST.getlist('vocab_book_ids[]')
            v_ranges = request.POST.getlist('vocab_ranges[]')
            v_scores = request.POST.getlist('vocab_scores[]')
            
            for i in range(len(v_ids)):
                if i < len(v_ranges) and v_ids[i] and v_ranges[i]:
                    rng = v_ranges[i].strip()
                    # 검사 없이 바로 저장
                    try:
                        ClassLogEntry.objects.create(
                            class_log=class_log,
                            wordbook_id=v_ids[i],
                            progress_range=rng,
                            score=v_scores[i].strip() if i < len(v_scores) else ''
                        )
                    except Exception as e:
                        print(f"저장 오류 (단어): {e}") # 디버깅용 로그
                        pass # 오류 나도 무시하고 다음 거 저장

        # 진도 저장
        m_ids = request.POST.getlist('main_book_ids[]')
        m_ranges = request.POST.getlist('main_ranges[]')
        m_scores = request.POST.getlist('main_scores[]')
        range_pattern = re.compile(r'^\d+(-\d+)?$')

        for i in range(len(m_ids)):
            if i < len(m_ranges) and m_ids[i] and m_ranges[i]:
                rng = m_ranges[i].strip()
                # 묻지도 따지지도 않고 바로 저장
                try:
                    ClassLogEntry.objects.create(
                        class_log=class_log,
                        textbook_id=m_ids[i],
                        progress_range=rng,
                        score=m_scores[i] if i < len(m_scores) else ''
                    )
                except Exception as e:
                    print(f"저장 오류 (진도): {e}")
                    pass

        # 과제 저장 (개선된 로직)
        hw_v_ids = request.POST.getlist('hw_vocab_book')
        hw_v_rngs = request.POST.getlist('hw_vocab_range')
        v_hw_list = []
        
        # 갯수가 안 맞을 수 있으므로 range 기준으로 반복
        for i in range(len(hw_v_rngs)):
            if hw_v_rngs[i].strip(): # 내용이 있을 때만 저장
                text = hw_v_rngs[i].strip()
                # 교재를 선택했다면 제목을 앞에 붙여줌
                if i < len(hw_v_ids) and hw_v_ids[i]:
                    try:
                        bk = WordBook.objects.get(id=hw_v_ids[i])
                        text = f"[{bk.title}] {text}"
                    except: pass
                v_hw_list.append(text)
        class_log.hw_vocab_range = " / ".join(v_hw_list)

        hw_m_ids = request.POST.getlist('hw_main_book_id')
        hw_m_rngs = request.POST.getlist('hw_main_range')
        m_hw_list = []
        
        for i in range(len(hw_m_rngs)):
            if hw_m_rngs[i].strip(): # 내용이 있을 때만 저장
                text = hw_m_rngs[i].strip()
                # 교재를 선택했다면 제목을 앞에 붙여줌
                if i < len(hw_m_ids) and hw_m_ids[i]:
                    try:
                        bk = Textbook.objects.get(id=hw_m_ids[i])
                        text = f"[{bk.title}] {text}"
                    except: pass
                m_hw_list.append(text)
        class_log.hw_main_range = " / ".join(m_hw_list)
        
        class_log.teacher_comment = request.POST.get('teacher_comment', '')
        class_log.save()

        if request.POST.get('send_notification') == 'on':
            send_homework_notification(class_log)
            class_log.notification_sent_at = timezone.now()
            class_log.save()
            messages.success(request, "일지 저장 및 알림톡 발송 완료!")
        else:
            messages.success(request, "일지가 저장되었습니다.")

        return redirect('academy:class_management')
    
    # --- GET 요청 처리 ---
    existing_log = ClassLog.objects.filter(student=student, date=target_date, subject=subject).first()
    is_reading_mode = (subject == 'READING')

    today_vocab_results = []
    if student.user:
        # [수정] 모델명 TestResult로 변경
        today_vocab_results = TestResult.objects.filter(
            student=student, # [수정] user=student.user 가 아니라 student=student (StudentProfile 사용)
            created_at__date=target_date
        ).prefetch_related('details', 'book').order_by('-created_at')

    context = {
        'schedule_id': schedule_id,
        'student': student,
        'target_date': target_date,
        'subject': subject,
        'is_reading_mode': is_reading_mode,
        'is_readonly': is_readonly,
        'vocab_books': vocab_books,
        'vocab_publishers': vocab_publishers,
        'vocab_books_json': json.dumps(vocab_books_dict),
        'syntax_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in syntax_books]),
        'reading_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in reading_books]),
        'grammar_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in grammar_books]),
        'school_exam_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in school_exam_books]),
        'prev_log': prev_log,       # (교차) 상대방 수업 정보
        'my_prev_log': my_prev_log, # (본인) 나의 지난 숙제 정보 [NEW]
        'today_vocab_results': today_vocab_results,
        'class_log': existing_log,
    }
    return render(request, 'academy/create_class_log.html', context)

def send_homework_notification(class_log):
    student = class_log.student
    
    # 1. 선생님 이름create_class_log
    teacher_name = "담임 선생님"
    if class_log.teacher:
        if hasattr(class_log.teacher, 'staff_profile'): 
            teacher_name = class_log.teacher.staff_profile.name
        else: 
            teacher_name = class_log.teacher.username

    # 2. 메시지 본문 (템플릿과 동일해야 함)
    message = f"[블라썸에듀] {student.name} 학생 오늘 수업 리포트\n\n📅 수업일: {class_log.date}\n🧑‍🏫 담당: {teacher_name}\n\n📝 [다음 과제 안내]\n"
    
    if class_log.hw_vocab_range:
        message += f"📕 단어 과제:\n{class_log.hw_vocab_range}\n"
    if class_log.hw_main_range:
        message += f"📘 교재 과제:\n{class_log.hw_main_range}\n"
    if class_log.teacher_comment:
        message += f"\n💬 선생님 말씀:\n{class_log.teacher_comment}\n"
    
    message += "\n꼼꼼하게 준비해서 다음 수업 때 만나요! 💪"
    
    # 3. 전송 대상: 학생 본인 우선, 없으면 어머님 번호
    target_phone = student.phone_number or student.parent_phone_mom
    
    if target_phone:
        # ⚠️ WAITING_CODE_HOMEWORK 부분은 나중에 승인된 템플릿 코드로 바꿔야 합니다.
        send_alimtalk(
            receiver_phone=target_phone,
            template_code="WAITING_CODE_HOMEWORK", 
            context_data={'content': message}
        )