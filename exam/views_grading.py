from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import TestPaper, ExamResult, ExamResultDetail

@login_required
def grading_list(request):
    """
    성적 입력 대기 중인 시험지 목록을 보여줍니다.
    """
    # 아직 결과가 없는 시험지거나, 이미 있지만 수정하고 싶은 경우 모두 표시
    # 최신순 정렬
    papers = TestPaper.objects.select_related('student').order_by('-created_at')
    
    # 각 시험지별로 성적 입력 여부 확인
    paper_list = []
    for paper in papers:
        result = ExamResult.objects.filter(paper=paper).first()
        paper_list.append({
            'paper': paper,
            'is_graded': result is not None,
            'score': result.score if result else None
        })

    return render(request, 'exam/grading_list.html', {'paper_list': paper_list})

@login_required
def grading_form(request, paper_id):
    """
    실제 O/X를 입력하는 화면
    """
    paper = get_object_or_404(TestPaper, id=paper_id)
    
    # [중요] 시험지 출력 때와 똑같은 순서로 정렬해야 입력이 편함
    all_qs = paper.questions.all()
    
    # 1. 구문 (S1)
    s1_questions = sorted(
        [q for q in all_qs if q.category != 'READING'],
        key=lambda q: (0 if q.style == 'CONCEPT' else 1, q.chapter, q.number)
    )
    # 2. 독해 (S2)
    s2_questions = sorted(
        [q for q in all_qs if q.category == 'READING'],
        key=lambda q: (0 if q.style == 'CONCEPT' else 1, q.chapter, q.number)
    )
    
    # 전체 문제 리스트 합치기 (순서 보장)
    ordered_questions = s1_questions + s2_questions
    total_count = len(ordered_questions)

    if request.method == 'POST':
        with transaction.atomic():
            # 1. 결과(ExamResult) 객체 생성 or 가져오기
            result, created = ExamResult.objects.get_or_create(
                student=paper.student,
                paper=paper
            )
            
            # 2. 기존 상세 데이터가 있다면 삭제 (재채점 시)
            result.detail_set.all().delete()
            
            correct_count = 0
            details = []
            
            # 3. O/X 입력 처리
            for q in ordered_questions:
                # 체크박스 값 확인 (name="q_문제ID")
                is_correct = request.POST.get(f'q_{q.id}') == 'on'
                
                if is_correct:
                    correct_count += 1
                
                details.append(ExamResultDetail(
                    result=result,
                    question=q,
                    is_correct=is_correct,
                    student_answer="O" if is_correct else "X" # 간소화
                ))
            
            # 4. 상세 데이터 저장 (Bulk Create)
            ExamResultDetail.objects.bulk_create(details)
            
            # 5. 총점 계산 (100점 만점 환산)
            if total_count > 0:
                final_score = int((correct_count / total_count) * 100)
            else:
                final_score = 0
            
            result.score = final_score
            result.save()
            
            messages.success(request, f"✅ 채점 완료! 점수: {final_score}점")
            return redirect('exam:grading_list')

    return render(request, 'exam/grading_form.html', {
        'paper': paper,
        'questions': ordered_questions,
        'total_count': total_count
    })