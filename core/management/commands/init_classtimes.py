from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_time
from datetime import datetime, timedelta, time
from core.models import ClassTime, Branch

class Command(BaseCommand):
    help = '구문 및 독해 수업 시간표 데이터를 일괄 생성합니다.'

    def add_arguments(self, parser):
        # 기존 데이터를 지우고 새로 만들지 여부를 옵션으로 받음
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 시간표 데이터를 모두 삭제하고 새로 생성합니다.',
        )

    def handle(self, *args, **options):
        # 1. 기존 데이터 삭제 옵션 확인
        if options['clear']:
            self.stdout.write(self.style.WARNING('기존 시간표 데이터를 삭제하는 중...'))
            ClassTime.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('삭제 완료.'))

        # 2. 적용할 요일 및 지점 설정
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        branches = Branch.objects.all()

        if not branches.exists():
            self.stdout.write(self.style.ERROR('등록된 지점(Branch)이 없습니다. 지점을 먼저 생성해주세요.'))
            return

        total_created = 0

        # 3. 시간 생성 로직 정의
        for branch in branches:
            self.stdout.write(f"[{branch.name}] 시간표 생성 시작...")
            
            for day in days:
                # ==========================================
                # A. 구문 (Syntax) 시간표 생성
                # ==========================================
                # 규칙 1: 오전 (09:00 시작 ~ 12:20 시작이 마지막) -> 간격 40분
                # 규칙 2: 오후 (13:20 시작 ~ 20:40 시작이 마지막) -> 간격 40분
                
                # 오전 루프
                current_time = datetime.strptime("09:00", "%H:%M")
                morning_end_limit = datetime.strptime("12:20", "%H:%M") # 12:20 시작이 막타임
                
                while current_time <= morning_end_limit:
                    start = current_time.time()
                    end_dt = current_time + timedelta(minutes=40)
                    end = end_dt.time()
                    
                    self.create_class_time(branch, day, start, end, "구문")
                    current_time = end_dt # 40분 뒤가 다음 타임 시작

                # 오후 루프
                current_time = datetime.strptime("13:20", "%H:%M") # 점심시간 20분 후 시작
                afternoon_end_limit = datetime.strptime("20:40", "%H:%M") # 20:40 시작이 막타임

                while current_time <= afternoon_end_limit:
                    start = current_time.time()
                    end_dt = current_time + timedelta(minutes=40)
                    end = end_dt.time()

                    self.create_class_time(branch, day, start, end, "구문")
                    current_time = end_dt

                # ==========================================
                # B. 독해 (Reading) 시간표 생성
                # ==========================================
                # 규칙: 09:00 시작 ~ 20:30 시작이 마지막 -> 간격 30분
                
                current_time = datetime.strptime("09:00", "%H:%M")
                reading_end_limit = datetime.strptime("20:30", "%H:%M")

                while current_time <= reading_end_limit:
                    start = current_time.time()
                    end_dt = current_time + timedelta(minutes=30)
                    end = end_dt.time()

                    self.create_class_time(branch, day, start, end, "독해")
                    current_time = end_dt

        self.stdout.write(self.style.SUCCESS('모든 시간표 생성이 완료되었습니다.'))

    def create_class_time(self, branch, day, start, end, type_name):
        """중복 방지하며 ClassTime 생성"""
        # 이름은 "구문 09:00" 형식으로 자동 생성 (관리 편의상)
        name = f"{type_name} {start.strftime('%H:%M')}"
        
        obj, created = ClassTime.objects.get_or_create(
            branch=branch,
            day=day,
            start_time=start,
            end_time=end,
            defaults={'name': name}
        )
        if created:
            # print(f"  + 생성: {branch} {day} {name}") # 너무 로그가 많으면 주석 처리
            pass