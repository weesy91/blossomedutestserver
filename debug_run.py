# debug_run.py
import os
import cv2
# mock.omr 에서 scan_omr 함수 가져오기 (경로 주의)
# 같은 폴더에 있다면 from omr import scan_omr
# 프로젝트 루트라면 아래처럼 설정
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mock.omr import scan_omr

file_path = 'test_omr.png' # 테스트할 이미지 파일명 (확장자 확인!)

if os.path.exists(file_path):
    print(f"📸 {file_path} 디버깅 모드로 분석 시작...")
    
    with open(file_path, 'rb') as f:
        # debug_mode=True로 설정하여 이미지 생성 유도
        answers = scan_omr(f, debug_mode=True)
    
    print(f"✅ 분석 완료! 결과 개수: {len(answers) if answers else 0}")
    print(f"결과: {answers}")
    print("📂 'debug_result.jpg' 파일을 열어서 녹색 박스가 잘 쳐졌는지 확인하세요!")
else:
    print("파일이 없습니다.")