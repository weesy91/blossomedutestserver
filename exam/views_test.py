from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Question, TestPaper
from core.models import StudentProfile # [수정] StudentUser 대신 Profile 사용

@login_required
def create_test_paper(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        s1_ids_raw = request.POST.get('s1_ids', '')
        s2_ids_raw = request.POST.get('s2_ids', '')
        custom_title = request.POST.get('title')

        # 1. 학생 프로필 확인 (User를 거치지 않고 바로 Profile 조회)
        try:
            target_profile = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return HttpResponse("❌ 존재하지 않는 학생 ID입니다.", status=404)

        # 2. 시험지 생성
        paper = TestPaper.objects.create(
            student=target_profile, # Profile 객체 할당
            title=custom_title or f"{target_profile.name} 월말평가",
            target_chapters="마법사 출제"
        )

        # 3. 문제 연결
        s1_ids = [int(i) for i in s1_ids_raw.split(',') if i]
        s2_ids = [int(i) for i in s2_ids_raw.split(',') if i]
        all_ids = s1_ids + s2_ids
        
        if all_ids:
            paper.questions.set(Question.objects.filter(id__in=all_ids))

        return redirect('exam:print_test_paper', paper_id=paper.id)
    
    return redirect('exam:exam_wizard')

@login_required
def print_test_paper(request, paper_id):
    paper = get_object_or_404(TestPaper, id=paper_id)
    all_qs = paper.questions.all()
    
    # 문제 정렬 (개념 -> 분석 순, 그리고 챕터/번호 순)
    s1_questions = sorted(
        [q for q in all_qs if q.category != 'READING'],
        key=lambda q: (0 if q.style == 'CONCEPT' else 1, q.chapter, q.number)
    )
    
    s2_questions = sorted(
        [q for q in all_qs if q.category == 'READING'],
        key=lambda q: (0 if q.style == 'CONCEPT' else 1, q.chapter, q.number)
    )
    
    return render(request, 'exam/print_test_paper.html', {
        'paper': paper,
        's1_questions': s1_questions,
        's2_questions': s2_questions,
        'total_count': all_qs.count()
    })