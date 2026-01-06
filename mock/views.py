# mock/views.py
import platform, json # [필수] OS 확인용 (윈도우/리눅스 구분)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone
from core.models import StudentProfile
from .models import MockExam, MockExamInfo, MockExamQuestion
from .forms import MockExamForm
from .omr import scan_omr, calculate_score

# ---------------------------------------------------------
# [Helper] Poppler 경로 설정 함수
# ---------------------------------------------------------
def get_poppler_path():
    """
    OS에 따라 Poppler 경로를 다르게 반환합니다.
    - Windows: 개발자 PC의 로컬 경로 반환 (수정 필요!)
    - Linux(Lightsail): None 반환 (시스템 경로 사용)
    """
    system_name = platform.system()
    
    if system_name == 'Windows':
        # ⚠️ 본인 컴퓨터의 Poppler bin 폴더 경로로 수정해주세요!
        # r"..." 을 사용해야 경로 에러가 안 납니다.
        return r"C:\Program Files (x86)\poppler\Library\bin"  
    else:
        # 리눅스 서버(Lightsail)에서는 'apt-get install poppler-utils'로 설치하므로
        # 별도 경로 지정이 필요 없습니다.
        return None

# ---------------------------------------------------------
# [View] 학생 목록 및 개별 입력
# ---------------------------------------------------------
@login_required
def student_list(request):
    user = request.user
    search_query = request.GET.get('q', '')

    if user.is_superuser or (hasattr(user, 'staff_profile') and user.staff_profile.position == 'PRINCIPAL'):
        students = StudentProfile.objects.all().order_by('name')
    elif hasattr(user, 'staff_profile'):
        if user.staff_profile.position == 'VICE':
            team_teachers = list(user.staff_profile.managed_teachers.all()) + [user]
            students = StudentProfile.objects.filter(
                Q(syntax_teacher__in=team_teachers) | 
                Q(reading_teacher__in=team_teachers) |
                Q(extra_class_teacher__in=team_teachers)
            ).distinct().order_by('name')
        else:
            students = StudentProfile.objects.filter(
                Q(syntax_teacher=user) | 
                Q(reading_teacher=user) | 
                Q(extra_class_teacher=user)
            ).distinct().order_by('name')
    else:
        students = StudentProfile.objects.none()

    if search_query:
        students = students.filter(name__icontains=search_query)

    return render(request, 'mock/student_list.html', {
        'students': students,
        'search_query': search_query
    })

@login_required
def input_score(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    
    # 1. 활성화된 시험지 목록 가져오기
    exams = MockExamInfo.objects.filter(is_active=True).order_by('-year', '-month')
    
    # 2. 시험지별 문항 정보 로드
    exam_data = {}
    for exam in exams:
        q_dict = {}
        for q in exam.questions.all():
            q_dict[q.number] = {'score': q.score, 'type': q.category}
        exam_data[exam.id] = q_dict

    # [수정됨] 3. 기본 표준 맵핑 (여기가 READING으로 되어 있어서 문제였습니다!)
    # 13개 상세 유형으로 다시 정의합니다.
    standard_map = {}
    for i in range(1, 46):
        if 1 <= i <= 17: cat = 'LISTENING'   # 듣기
        elif i in [18, 19]: cat = 'PURPOSE'  # 목적/심경
        elif i in [20, 21, 22, 23, 24]: cat = 'TOPIC' # 대의파악 (주장/함축/요지/주제/제목)
        elif i in [25, 26, 27, 28]: cat = 'DATA' # 실용문/일치
        elif i == 29: cat = 'GRAMMAR'        # 어법
        elif i == 30: cat = 'VOCAB'          # 어휘
        elif i in [31, 32, 33, 34]: cat = 'BLANK' # 빈칸추론
        elif i == 35: cat = 'FLOW'           # 무관한문장
        elif i in [36, 37]: cat = 'ORDER'    # 글의순서
        elif i in [38, 39]: cat = 'INSERT'   # 문장삽입
        elif i == 40: cat = 'SUMMARY'        # 요약문
        elif 41 <= i <= 45: cat = 'LONG'     # 장문독해
        else: cat = 'TOPIC'                  # 예외 처리
        
        standard_map[i] = cat

    if request.method == 'POST':
        form = MockExamForm(request.POST)
        if form.is_valid():
            mock_exam = form.save(commit=False)
            mock_exam.student = student
            mock_exam.recorded_by = request.user
            
            raw_wrong_ids = request.POST.get('wrong_question_numbers_str', '')
            if raw_wrong_ids:
                mock_exam.wrong_question_numbers = [int(x) for x in raw_wrong_ids.split(',') if x]
            else:
                mock_exam.wrong_question_numbers = []

            mock_exam.save()
            messages.success(request, f"{student.name} 학생 성적 저장 완료!")
            return redirect('mock:student_list')
    else:
        form = MockExamForm()
    
    recent_exams = MockExam.objects.filter(student=student).order_by('-exam_date')[:3]
    
    return render(request, 'mock/input_form.html', {
        'student': student, 
        'form': form, 
        'recent_exams': recent_exams,
        'exams': exams, 
        'exam_data_json': json.dumps(exam_data),
        'standard_map_json': json.dumps(standard_map) 
    })

@login_required
def bulk_omr_upload(request):
    if request.method == 'POST':
        exam_id = request.POST.get('exam_info_id')
        uploaded_file = request.FILES.get('omr_file')
        
        if not exam_id or not uploaded_file:
            messages.error(request, "시험 정보와 파일을 모두 선택해주세요.")
            return redirect('mock:bulk_upload')

        exam_info = get_object_or_404(MockExamInfo, id=exam_id)
        logs, success_count, fail_count = [], 0, 0

        try:
            filename = uploaded_file.name.lower()
            images = []
            
            if filename.endswith('.pdf'):
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(uploaded_file.read(), poppler_path=get_poppler_path())
                except ImportError:
                    messages.error(request, "pdf2image 모듈이 없습니다.")
                    return redirect('mock:bulk_upload')
                except Exception as e:
                    messages.error(request, f"PDF 변환 오류: {e}")
                    return redirect('mock:bulk_upload')
            else:
                from PIL import Image
                images = [Image.open(uploaded_file)]

            for i, pil_image in enumerate(images):
                import io
                img_byte_arr = io.BytesIO()
                pil_image.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()

                # [수정] scan_omr 호출 (디버그 모드는 필요시 True로 변경)
                # 실제 운영시에는 False로 두는 것이 성능상 좋습니다.
                student_id_str, answers = scan_omr(img_bytes, debug_mode=False)
                
                if not student_id_str or len(student_id_str) < 4 or "?" in student_id_str:
                    logs.append(f"PAGE {i+1}: ⚠️ 수험번호 인식 실패 (값: {student_id_str})")
                    fail_count += 1
                    continue
                
                try:
                    student = StudentProfile.objects.get(attendance_code=student_id_str)
                except StudentProfile.DoesNotExist:
                    logs.append(f"PAGE {i+1}: ❌ 학생 없음 (번호: {student_id_str})")
                    fail_count += 1
                    continue

                if not answers or len(answers) < 10:
                     logs.append(f"PAGE {i+1}: ⚠️ 답안 인식 실패 (개수: {len(answers)}) - {student.name}")
                     fail_count += 1
                     continue

                result = calculate_score(answers, exam_info)
                
                MockExam.objects.create(
                    student=student,
                    title=exam_info.title,
                    exam_date=timezone.now().date(),
                    score=result['score'],
                    grade=result['grade'],
                    student_answers=result['student_answers_dict'],
                    wrong_question_numbers=result['wrong_question_numbers'],
                    wrong_listening=result['wrong_counts']['LISTENING'],
                    wrong_vocab=result['wrong_counts']['VOCAB'],
                    wrong_grammar=result['wrong_counts']['GRAMMAR'],
                    wrong_reading=result['wrong_counts']['READING'],
                    recorded_by=request.user
                )
                success_count += 1
                logs.append(f"PAGE {i+1}: ✅ {student.name} ({result['score']}점)")

            summary = f"총 {len(images)}장 처리: 성공 {success_count}, 실패 {fail_count}"
            return render(request, 'mock/bulk_upload.html', {
                'exams': MockExamInfo.objects.filter(is_active=True).order_by('-created_at'),
                'logs': logs, 'summary': summary
            })

        except Exception as e:
            messages.error(request, f"처리 중 오류: {e}")
            return redirect('mock:bulk_upload')

    exams = MockExamInfo.objects.filter(is_active=True).order_by('-year', '-month')
    return render(request, 'mock/bulk_upload.html', {'exams': exams})
