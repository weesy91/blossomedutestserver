from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
import json
import re

from academy.models import TemporarySchedule, Textbook, ClassLog, ClassLogEntry
from vocab.models import WordBook
from core.models import StudentProfile

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

    # ==========================================================================
    # [보안] 권한 체크: 담당 과목 선생님만 작성 가능 (원장/부원장 예외)
    # ==========================================================================
    is_admin = request.user.is_superuser or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.position == 'VICE')
    
    if student and not is_admin:
        # 1. 구문 수업인데, 로그인한 사람이 구문 담당 쌤이 아닌 경우
        if subject == 'SYNTAX' and student.syntax_teacher != request.user:
            messages.error(request, "🚫 구문 담당 선생님만 작성할 수 있습니다.")
            return redirect('academy:class_management')
            
        # 2. 독해 수업인데, 로그인한 사람이 독해 담당 쌤이 아닌 경우
        elif subject == 'READING' and student.reading_teacher != request.user:
            messages.error(request, "🚫 독해 담당 선생님만 작성할 수 있습니다.")
            return redirect('academy:class_management')
    # ==========================================================================

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
    vocab_books = WordBook.objects.select_related('publisher').all()
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
                    if range_pattern.match(rng):
                        ClassLogEntry.objects.create(
                            class_log=class_log,
                            wordbook_id=v_ids[i],
                            progress_range=rng,
                            score=v_scores[i].strip() if i < len(v_scores) else None
                        )

        # 진도 저장
        m_ids = request.POST.getlist('main_book_ids[]')
        m_ranges = request.POST.getlist('main_ranges[]')
        m_scores = request.POST.getlist('main_scores[]')
        range_pattern = re.compile(r'^\d+(-\d+)?$')

        for i in range(len(m_ids)):
            if i < len(m_ranges) and m_ids[i] and m_ranges[i]:
                rng = m_ranges[i].strip()
                if range_pattern.match(rng):
                    ClassLogEntry.objects.create(
                        class_log=class_log,
                        textbook_id=m_ids[i],
                        progress_range=rng,
                        score=m_scores[i] if i < len(m_scores) else ''
                    )

        # 과제 저장
        hw_v_ids = request.POST.getlist('hw_vocab_book')
        hw_v_rngs = request.POST.getlist('hw_vocab_range')
        v_hw_list = []
        for i in range(len(hw_v_ids)):
            if i < len(hw_v_rngs) and hw_v_ids[i] and hw_v_rngs[i]:
                try:
                    bk = WordBook.objects.get(id=hw_v_ids[i])
                    v_hw_list.append(f"[{bk.title}] {hw_v_rngs[i]}")
                except: pass
        class_log.hw_vocab_range = " / ".join(v_hw_list)

        hw_m_ids = request.POST.getlist('hw_main_book_id')
        hw_m_rngs = request.POST.getlist('hw_main_range')
        m_hw_list = []
        for i in range(len(hw_m_ids)):
            if i < len(hw_m_rngs) and hw_m_ids[i] and hw_m_rngs[i]:
                try:
                    bk = Textbook.objects.get(id=hw_m_ids[i])
                    m_hw_list.append(f"[{bk.title}] {hw_m_rngs[i]}")
                except: pass
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
    existing_log = ClassLog.objects.filter(student=student, date=target_date).first()
    is_reading_mode = (subject == 'READING')

    context = {
        'schedule_id': schedule_id,
        'student': student,
        'target_date': target_date,
        'subject': subject,
        'is_reading_mode': is_reading_mode,
        'vocab_books': vocab_books,
        'vocab_publishers': vocab_publishers,
        'vocab_books_json': json.dumps(vocab_books_dict),
        'syntax_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in syntax_books]),
        'reading_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in reading_books]),
        'grammar_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in grammar_books]),
        'school_exam_books_json': json.dumps([{'id':b.id, 'title':b.title} for b in school_exam_books]),
        'prev_log': prev_log,       # (교차) 상대방 수업 정보
        'my_prev_log': my_prev_log, # (본인) 나의 지난 숙제 정보 [NEW]
        'class_log': existing_log,
    }
    return render(request, 'academy/create_class_log.html', context)

def send_homework_notification(class_log):
    student_name = class_log.student.name 
    teacher_name = "담임 선생님"
    if class_log.teacher:
        if hasattr(class_log.teacher, 'staff_profile'): teacher_name = class_log.teacher.staff_profile.name
        else: teacher_name = class_log.teacher.username

    message = f"[블라썸에듀] {student_name} 학생 오늘 수업 리포트\n\n📅 수업일: {class_log.date}\n🧑‍🏫 담당: {teacher_name}\n\n📝 [다음 과제 안내]\n"
    
    if class_log.hw_vocab_range:
        message += f"📕 단어 과제:\n{class_log.hw_vocab_range}\n"
    if class_log.hw_main_range:
        message += f"📘 교재 과제:\n{class_log.hw_main_range}\n"
    if class_log.teacher_comment:
        message += f"\n💬 선생님 말씀:\n{class_log.teacher_comment}\n"
    
    message += "\n꼼꼼하게 준비해서 다음 수업 때 만나요! 💪"
    print(f"\n{'='*20} [카톡 발송] {'='*20}\n{message}\n{'='*50}\n")