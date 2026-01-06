from django.http import JsonResponse 
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from core.models import StudentProfile
from exam.models import Question

# 4. API
@login_required
def get_students_by_teacher(request):
    teacher_id = request.GET.get('teacher_id')
    if not teacher_id: return JsonResponse({'students': []})
    try:
        students = StudentProfile.objects.filter(
            Q(syntax_teacher_id=teacher_id) | Q(reading_teacher_id=teacher_id) | Q(extra_class_teacher_id=teacher_id)
        ).select_related('school').distinct().values('id', 'name', 'school__name')
        data = [{'id': s['id'], 'name': f"{s['name']} ({s['school__name'] or '학교미정'})"} for s in students]
        data.sort(key=lambda x: x['name'])
        return JsonResponse({'students': data})
    except: return JsonResponse({'students': []})

    # exam/views_api.py 맨 아래에 추가


def get_questions_api(request):
    """마법사 화면에서 교재/범위 선택 시 문제 목록을 반환하는 API"""
    book_id = request.GET.get('book')
    start_raw = request.GET.get('start')
    end_raw = request.GET.get('end')
    
    # [디버깅용 로그] 서버 터미널에서 확인 가능
    print(f"🔍 검색 요청: Book={book_id}, Start={start_raw}, End={end_raw}")

    # 1. 빈 값이면 기본값 설정
    if not start_raw or start_raw == '': start_raw = '1'
    if not end_raw or end_raw == '': end_raw = '999'

    # 2. [핵심 수정] 문자열을 반드시 '숫자(int)'로 변환해야 DB가 인식함
    try:
        start = int(start_raw)
        end = int(end_raw)
    except ValueError:
        start = 1
        end = 999

    # 3. DB 검색
    questions = Question.objects.filter(
        textbook_id=book_id,  
        chapter__gte=start,
        chapter__lte=end
    ).order_by('chapter', 'number')
    
    print(f"✅ 검색 결과: {questions.count()}개 찾음") # 로그 확인용

    data = []
    for q in questions:
        data.append({
            'id': q.id,
            'chapter': q.chapter,
            'number': q.number,
            'style': q.style,
            'reading_type': q.reading_type,
        })
    
    return JsonResponse({'questions': data})