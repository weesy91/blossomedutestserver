from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, time, timedelta
from core.models import Branch, School, ClassTime, StudentProfile, StaffProfile
from academy.models import Attendance
from django.db import transaction
import random

User = get_user_model()

class Command(BaseCommand):
    help = '테스트용 대량의 데이터(시간표, 선생님, 다수의 학생)를 자동으로 생성합니다.'

    def add_minutes(self, t, minutes):
        """시간 더하기 헬퍼 함수"""
        total_minutes = t.hour * 60 + t.minute + minutes
        new_hour = (total_minutes // 60) % 24
        new_minute = total_minutes % 60
        return time(new_hour, new_minute)

    def create_class_times(self, branch, day_code, day_name, start_time, limit_time, interval_minutes, subject_name):
        """시간표 생성 헬퍼"""
        current = start_time
        count = 0
        while current <= limit_time:
            end_time = self.add_minutes(current, interval_minutes)
            name = f"[{subject_name}] {day_name} {current.strftime('%H:%M')}"
            
            ClassTime.objects.get_or_create(
                branch=branch,
                day=day_code,
                start_time=current,
                end_time=end_time,
                defaults={'name': name}
            )
            count += 1
            current = self.add_minutes(current, interval_minutes)
        return count

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("--- [1] 기초 데이터 생성 시작 ---")

        branch, _ = Branch.objects.get_or_create(name='동탄 본점')
        school, _ = School.objects.get_or_create(name='테스트고등학교', region='동탄')
        school.branches.add(branch)

        self.stdout.write("--- [2] 시간표 자동 생성 중... ---")
        day_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        day_names = {0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'}
        
        total_slots = 0
        
        # 2-1. 구문 (40분 간격)
        for day_num in range(5): # 월~금
            total_slots += self.create_class_times(branch, day_map[day_num], day_names[day_num], time(16,0), time(20,40), 40, '구문')
        for day_num in [5, 6]: # 토,일
            total_slots += self.create_class_times(branch, day_map[day_num], day_names[day_num], time(9,0), time(12,20), 40, '구문')
            total_slots += self.create_class_times(branch, day_map[day_num], day_names[day_num], time(13,20), time(18,0), 40, '구문')

        # 2-2. 독해 (30분 간격)
        for day_num in range(5): # 월~금
            total_slots += self.create_class_times(branch, day_map[day_num], day_names[day_num], time(16,0), time(20,30), 30, '독해')
        for day_num in [5, 6]: # 토,일
            total_slots += self.create_class_times(branch, day_map[day_num], day_names[day_num], time(9,0), time(18,0), 30, '독해')

        self.stdout.write(f"✅ 시간표 {total_slots}개 생성 완료")

        # 3. 선생님 계정 생성
        self.stdout.write("--- [3] 선생님 계정 생성 ---")
        def create_staff(username, name, role, is_syntax=False, is_reading=False):
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
            else:
                user = User.objects.create_user(username=username, password='1234')
                user.is_staff = True
                if role == 'PRINCIPAL': user.is_superuser = True
                user.save()
            
            profile, _ = StaffProfile.objects.get_or_create(user=user)
            profile.name = name
            profile.branch = branch
            profile.position = role
            profile.is_syntax_teacher = is_syntax
            profile.is_reading_teacher = is_reading
            profile.save()
            return user, profile

        admin_u, admin_p = create_staff('admin', '원장님', 'PRINCIPAL', True, True)
        vice_u, vice_p = create_staff('vice', '부원장님', 'VICE', True, True)
        t_syn, t_syn_p = create_staff('t_syntax', '구문쌤', 'TEACHER', is_syntax=True, is_reading=False)
        t_read, t_read_p = create_staff('t_reading', '독해쌤', 'TEACHER', is_syntax=False, is_reading=True)

        # 관리 권한 부여
        vice_p.managed_teachers.add(t_syn, t_read)
        
        # 4. 학생 대량 생성 및 배정
        self.stdout.write("--- [4] 학생 대량 생성 및 배정 (20명) ---")
        
        # 테스트를 위해 '오늘' 요일에 맞는 시간표를 찾습니다.
        today = timezone.now().date()
        today_weekday = today.weekday() # 0~6
        today_code = day_map[today_weekday]
        
        # 오늘 요일의 모든 수업 시간표 리스트 가져오기
        today_syntax_slots = list(ClassTime.objects.filter(day=today_code, name__contains='구문').order_by('start_time'))
        today_reading_slots = list(ClassTime.objects.filter(day=today_code, name__contains='독해').order_by('start_time'))
        
        # 만약 오늘 수업이 없으면(새벽이거나 공휴일 등) 그냥 월요일로 대체
        if not today_syntax_slots: 
            today_code = 'Mon'
            today_syntax_slots = list(ClassTime.objects.filter(day='Mon', name__contains='구문').order_by('start_time'))
            today_reading_slots = list(ClassTime.objects.filter(day='Mon', name__contains='독해').order_by('start_time'))

        # 선생님 조합 정의
        teacher_combos = [
            (t_syn, t_read, '일반쌤'), # 0번: 일반쌤 (가중치 높게)
            (admin_u, admin_u, '원장님'), # 1번: 원장님
            (vice_u, vice_u, '부원장님') # 2번: 부원장님
        ]

        created_count = 0
        for i in range(1, 21): # 학생 20명 생성
            username = f'student_{i}'
            
            # 선생님 배정 (일반 60%, 원장 20%, 부원장 20%)
            t_choice = random.choices([0, 1, 2], weights=[6, 2, 2], k=1)[0]
            syn_teacher, read_teacher, t_label = teacher_combos[t_choice]
            
            student_name = f'학생{i}({t_label})'

            if User.objects.filter(username=username).exists():
                u = User.objects.get(username=username)
            else:
                u = User.objects.create_user(username=username, password='1234')
            
            # 시간표 배정
            # 구문(1:1): 슬롯이 많으므로 학생마다 순서대로 돌아가며 배정
            s_class = today_syntax_slots[i % len(today_syntax_slots)] if today_syntax_slots else None
            
            # 독해(1:N): 랜덤하게 배정 (여러 명이 겹치도록)
            r_class = random.choice(today_reading_slots) if today_reading_slots else None

            p, _ = StudentProfile.objects.get_or_create(user=u)
            p.branch = branch
            p.name = student_name
            p.school = school
            p.base_grade = random.choice([10, 11, 12]) # 고1~고3 랜덤
            p.phone_number = f'010-0000-{str(i).zfill(4)}'
            p.attendance_code = str(u.id).zfill(4)
            
            # 수업 정보 연결
            p.syntax_teacher = syn_teacher
            p.reading_teacher = read_teacher
            p.syntax_class = s_class
            p.reading_class = r_class
            p.save()
            created_count += 1

            # [핵심] 50% 확률로 오늘 출석 처리 (일지 작성 테스트용)
            if random.choice([True, False]):
                Attendance.objects.get_or_create(
                    student=p,
                    date=today,
                    defaults={
                        'status': 'PRESENT',
                        'check_in_time': timezone.now(),
                        'memo': '테스트 자동 출석'
                    }
                )

        self.stdout.write("---------------------------------------")
        self.stdout.write(f"🎉 대량 테스트 데이터 구축 완료!")
        self.stdout.write(f" - 학생 {created_count}명 생성 완료 (일부 출석 처리됨)")
        self.stdout.write(f" - 선생님 ID: admin, vice, t_syntax, t_reading (비번 1234)")
        self.stdout.write(f" - 학생 ID: student_1 ~ student_20 (비번 1234)")