# run_test.py
import os
import django
from django.conf import settings

# 장고 환경 설정 로드
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from mock.omr import scan_omr

# 이미지 파일 열기
file_path = 'test_omr.png' # 캡처한 이미지 파일명

if os.path.exists(file_path):
    print(f"📸 {file_path} 분석 시작...")
    with open(file_path, 'rb') as f:
        answers = scan_omr(f)
    
    if answers:
        print("\n✅ 분석 성공! 결과:")
        print(f"문항 수: {len(answers)}")
        print(f"답안: {answers}")
        
        # 3단 분리가 잘 됐는지 확인 (예: 21번 답이 중간에 잘 껴있는지)
        print("\n[구간별 확인]")
        print(f"1~5번: {answers[:5]}")
        print(f"21~25번: {answers[20:25]}")
        print(f"41~45번: {answers[40:]}")
    else:
        print("❌ 분석 실패")
else:
    print(f"파일을 찾을 수 없습니다: {file_path}")