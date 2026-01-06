from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.files.base import ContentFile
from pdf2image import convert_from_bytes
import re
import io
import platform
import shutil
from PIL import Image, ImageChops 

from .models import Question
from academy.models import Textbook

# [서버 배포 안전 장치]
# 윈도우는 고정 경로, 리눅스는 시스템 경로(None)를 사용하되 설치 여부를 체크함
if platform.system() == 'Windows':
    POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"
else:
    # 리눅스 환경: poppler-utils 설치 여부 확인
    if shutil.which("pdftoppm"):
        POPPLER_PATH = None 
    else:
        POPPLER_PATH = None
        print("⚠️ [경고] 서버에 poppler-utils가 설치되지 않은 것 같습니다. 'sudo apt-get install poppler-utils'를 실행해주세요.")

def trim_whitespace(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0,0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox: return im.crop(bbox)
    return im

@user_passes_test(lambda u: u.is_superuser)
def upload_images_bulk(request):
    academy_books = Textbook.objects.all().order_by('category', 'title')

    if request.method == 'POST':
        files = request.FILES.getlist('images')
        book_name = request.POST.get('book_name')
        default_style = request.POST.get('style') 
        reading_type_input = request.POST.get('reading_type', 'NONE')
        
        try:
            selected_book = Textbook.objects.get(title=book_name)
            category = selected_book.category
        except Textbook.DoesNotExist:
            messages.error(request, "존재하지 않는 교재입니다.")
            return redirect('exam:upload_images')

        if not files:
            messages.error(request, "파일을 선택해주세요.")
            return redirect('exam:upload_images')

        success_count = 0
        Image.MAX_IMAGE_PIXELS = None 

        for f in files:
            # 파일명에서 숫자 추출 (예: "1강.pdf" -> 1)
            numbers = re.findall(r'\d+', f.name)
            if not numbers: continue
            chapter = int(numbers[0])
            filename = f.name.lower()
            
            # 스타일 및 오프셋 초기화
            current_style = default_style
            start_offset = 0 
            
            # 파일명에 따른 스타일 자동 감지 (오버라이드)
            if '구문' in filename or '분석' in filename or 'syntax' in filename:
                current_style = 'ANALYSIS'
                start_offset = 500         
            elif '개념' in filename or 'concept' in filename:
                current_style = 'CONCEPT'
                start_offset = 0      

            # 독해 유형 처리
            current_reading_type = 'NONE'
            if category == 'READING':
                current_reading_type = reading_type_input 
                # 구조분석(S타입)이면 분석형으로 간주
                if current_reading_type == 'STRUCT':
                    current_style = 'ANALYSIS'
                    start_offset = 500
                else:
                    current_style = 'CONCEPT'
                    start_offset = 0

            is_answer = ('답' in filename or 'sol' in filename)

            if filename.endswith('.pdf'):
                try:
                    pages = convert_from_bytes(f.read(), poppler_path=POPPLER_PATH, dpi=200, strict=False, use_cropbox=True)
                    for i, page in enumerate(pages):
                        try:
                            question_number = (i + 1) + start_offset
                            page = page.convert('RGB')
                            page = trim_whitespace(page)
                            
                            img_byte_arr = io.BytesIO()
                            page.save(img_byte_arr, format='JPEG', quality=90)
                            
                            file_name_str = f"{chapter}_{question_number}_{current_style}.jpg"
                            content_file = ContentFile(img_byte_arr.getvalue(), name=file_name_str)
                            
                            if is_answer:
                                try:
                                    q = Question.objects.get(textbook=selected_book, chapter=chapter, number=question_number)
                                    q.answer_image = content_file
                                    q.save()
                                except Question.DoesNotExist: pass
                            else:
                                Question.objects.update_or_create(
                                    textbook=selected_book, chapter=chapter, number=question_number,
                                    defaults={
                                        'category': category, 
                                        'style': current_style,
                                        'reading_type': current_reading_type,
                                        'question_text': f"(PDF {chapter}강-{question_number})",
                                        'image': content_file
                                    }
                                )
                                success_count += 1
                        except Exception as inner_e: print(f"Page Error: {inner_e}")
                except Exception as e: messages.error(request, f"PDF Error: {e} (poppler 설치 확인 요망)")
            else:
                # 이미지 파일 처리 (기존 로직 유지)
                if len(numbers) >= 2:
                    raw_num = int(numbers[1])
                    if category == 'READING':
                        q_num = raw_num + start_offset
                    else:
                        q_num = raw_num + 500 if (current_style == 'ANALYSIS' and raw_num < 500) else raw_num
                    
                    if is_answer:
                        try:
                            q = Question.objects.get(textbook=selected_book, chapter=chapter, number=q_num)
                            q.answer_image = f
                            q.save()
                        except: pass
                    else:
                        Question.objects.update_or_create(
                            textbook=selected_book, chapter=chapter, number=q_num,
                            defaults={
                                'category': category, 
                                'style': current_style, 
                                'reading_type': current_reading_type,
                                'image': f
                            }
                        )
                        success_count += 1

        messages.success(request, f"✅ 총 {success_count}개 문항 저장 완료!")
        return redirect('exam:upload_images')
    
    return render(request, 'exam/upload_images.html', {'academy_books': academy_books})