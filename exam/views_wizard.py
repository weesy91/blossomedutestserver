from django.shortcuts import render, redirect, get_object_or_404  # [수정] redirect, get_object_or_404 추가
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse 
from core.models import StudentProfile
from academy.models import Textbook
from .models import Question, TestPaper  # [수정] TestPaper 모델 추가
from django.utils import timezone
from django.db import transaction
import calendar

@login_required
def exam_wizard(request):
    """
    월말평가 출제 마법사 페이지
    """
    # ==========================================
    # [NEW] 접속 권한 및 기간 체크 로직
    # ==========================================
    now = timezone.now()
    
    # 1. 이번 달 말일 계산
    last_day = calendar.monthrange(now.year, now.month)[1]
    
    # 2. 기간 시작일 계산 (말일 포함 7일 전)
    start_day = last_day - 7
    is_exam_period = (now.day >= start_day)

    # 3. [핵심] 기간이 아니면 튕겨내기 (단, 원장님(superuser)은 통과!)
    if not is_exam_period and not request.user.is_superuser:
        # 기간도 아니고, 원장님도 아니면 홈으로 돌려보냄
        return redirect('core:teacher_home')

    # ==========================================
    # 기존 로직 (데이터 로딩)
    # ==========================================
    students = StudentProfile.objects.select_related('user', 'school').order_by('name')
    textbooks = Textbook.objects.all()

    context = {
        'students': students,
        'textbooks': textbooks,
    }
    return render(request, 'exam/exam_wizard.html', context)

# 👇 문제 검색 API
@login_required
def api_get_questions(request):
    book_title = request.GET.get('book')
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    # 기본 쿼리셋
    qs = Question.objects.select_related('textbook').all()
    
    # 필터링
    if book_title:
        qs = qs.filter(textbook__title=book_title)
    if start:
        qs = qs.filter(chapter__gte=start)
    if end:
        qs = qs.filter(chapter__lte=end)
        
    # 정렬 (강 -> 번호 순)
    qs = qs.order_by('chapter', 'number')
    
    # JSON 변환
    data = []
    for q in qs:
        data.append({
            'id': q.id,
            'chapter': q.chapter,
            'number': q.number,
            'style': q.style,         # CONCEPT / ANALYSIS
            'category': q.category,   # READING / SYNTAX
            'reading_type': q.reading_type or '',
        })
        
    return JsonResponse({'questions': data})

@login_required
@transaction.atomic
def exam_create(request):
    """
    마법사에서 선택한 문제들로 실제 시험지(TestPaper)를 생성합니다.
    """
    if request.method == 'POST':
        # 1. HTML 폼에서 데이터 꺼내기
        student_id = request.POST.get('student_id')
        title = request.POST.get('title')
        s1_ids_str = request.POST.get('s1_ids', '')  # "1,2,3" 형태의 문자열
        s2_ids_str = request.POST.get('s2_ids', '')

        # 2. 데이터 정제 (빈 문자열 처리 및 리스트 변환)
        s1_ids = [int(i) for i in s1_ids_str.split(',') if i.isdigit()]
        s2_ids = [int(i) for i in s2_ids_str.split(',') if i.isdigit()]
        
        all_ids = s1_ids + s2_ids

        # 3. 필수 정보 체크
        if not student_id or not title or not all_ids:
            # 에러 시 다시 마법사로 (실제론 JS에서 막지만 한번 더 체크)
            return redirect('exam:exam_wizard')

        # 4. DB에 저장
        student = get_object_or_404(StudentProfile, id=student_id)
        
        # (1) 시험지 껍데기 생성
        paper = TestPaper.objects.create(
            student=student,
            title=title,
            target_chapters="월말평가" # 임시
        )
        
        # (2) 문제 알맹이 연결 (Many-to-Many)
        questions = Question.objects.filter(id__in=all_ids)
        paper.questions.add(*questions)
        
        # 5. 생성 완료 후 PDF 출력 페이지로 이동
        # 주의: urls.py에 'test_paper_pdf'라는 이름의 URL이 있어야 합니다.
        return redirect('exam:test_paper_pdf', paper_id=paper.id)

    # POST가 아니면 마법사로 돌려보냄
    return redirect('exam:exam_wizard')