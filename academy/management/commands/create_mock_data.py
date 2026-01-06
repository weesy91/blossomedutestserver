import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from faker import Faker

# [주의] ClassLogEntry가 있다면 추가 import가 필요하지만, 일단 ClassLog만 사용합니다.
from core.models import StudentProfile, StaffProfile, Branch, School, ClassTime
from academy.models import Textbook, Attendance, ClassLog
from vocab.models import WordBook, Word, TestResult
from exam.models import Question, TestPaper, ExamResult, ExamResultDetail

class Command(BaseCommand):
    help = '테스트용 가상 데이터를 생성합니다. (학생, 교재, 문제, 성적 등)'

    def handle(self, *args, **options):
        fake = Faker('ko_KR')
        self.stdout.write("🛠️ 가상 데이터 생성을 시작합니다...")

        # 0. 기초 데이터 (지점, 학교, 시간표)
        branch, _ = Branch.objects.get_or_create(name='본원')
        school, _ = School.objects.get_or_create(name='블라썸고등학교', defaults={'region': '동탄'})
        
        class_syntax, _ = ClassTime.objects.get_or_create(
            name='고1 구문A반', day='Mon', 
            defaults={'branch': branch, 'start_time': '18:00', 'end_time': '20:00'}
        )
        class_reading, _ = ClassTime.objects.get_or_create(
            name='고1 독해A반', day='Tue', 
            defaults={'branch': branch, 'start_time': '18:00', 'end_time': '20:00'}
        )

        # 1. 선생님 계정 생성
        teacher_user, created = User.objects.get_or_create(username='teacher1', defaults={'email': 't1@test.com'})
        if created:
            teacher_user.set_password('1234')
            teacher_user.save()
            StaffProfile.objects.create(
                user=teacher_user, name='김선생', position='TEACHER', branch=branch,
                is_syntax_teacher=True, is_reading_teacher=True
            )
            self.stdout.write("✅ 선생님(teacher1/1234) 생성 완료")
        else:
            teacher_user = User.objects.get(username='teacher1')

        # 2. 학생 생성 (3명)
        students = []
        for i in range(1, 4):
            username = f'student{i}'
            u, _ = User.objects.get_or_create(username=username)
            u.set_password('1234')
            u.save()
            
            s, _ = StudentProfile.objects.get_or_create(
                user=u,
                defaults={
                    'name': fake.name(),
                    'phone_number': f'010-0000-000{i}',
                    'parent_phone_mom': f'010-9999-999{i}',
                    'school': school,
                    'branch': branch,
                    'base_grade': 10,
                    'base_year': timezone.now().year,
                    'syntax_teacher': teacher_user,
                    'reading_teacher': teacher_user,
                    'syntax_class': class_syntax,
                    'reading_class': class_reading
                }
            )
            students.append(s)
        self.stdout.write(f"✅ 학생 3명 생성 완료 ({', '.join([s.name for s in students])})")

        # 3. 교재 및 단어장 생성
        syntax_book, _ = Textbook.objects.get_or_create(title='천일문 기본', defaults={'category': 'SYNTAX'})
        reading_book, _ = Textbook.objects.get_or_create(title='자이스토리 독해', defaults={'category': 'READING'})
        word_book, _ = WordBook.objects.get_or_create(title='능률 보카', defaults={'uploaded_by': teacher_user})
        
        if not Word.objects.filter(book=word_book).exists():
            words = []
            for i in range(50):
                eng = fake.unique.word()
                words.append(Word(book=word_book, number=i//10+1, english=eng, korean=fake.word()))
            Word.objects.bulk_create(words, ignore_conflicts=True)
            self.stdout.write("✅ 단어 데이터 50개 생성")

        # 4. 시험 문제(Question) 데이터 생성
        if not Question.objects.exists():
            qs_list = []
            for ch in range(1, 11):
                for num in range(1, 11):
                    qs_list.append(Question(
                        textbook=syntax_book, category='SYNTAX', chapter=ch, number=num, style='ANALYSIS',
                        question_text=f"{ch}강 {num}번 구문 분석 문제입니다."
                    ))
            types = ['TOPIC', 'LOGIC', 'BLANK', 'DETAIL']
            for ch in range(1, 11):
                for num in range(1, 11):
                    qs_list.append(Question(
                        textbook=reading_book, category='READING', chapter=ch, number=num, style='CONCEPT',
                        reading_type=random.choice(types),
                        question_text=f"{ch}강 {num}번 독해 지문입니다."
                    ))
            Question.objects.bulk_create(qs_list, ignore_conflicts=True)
            self.stdout.write(f"✅ 시험 문제 {len(qs_list)}개 생성")

        # 5. 성적/출결 데이터 생성
        now = timezone.now()
        year = now.year
        month = now.month
        today = now.date()
        start_date = today.replace(day=1)
        
        for student in students:
            # (1) 출석
            curr = start_date
            while curr <= today:
                if curr.weekday() < 5:
                    status = random.choice(['PRESENT', 'PRESENT', 'PRESENT', 'LATE', 'ABSENT'])
                    Attendance.objects.get_or_create(student=student, date=curr, defaults={'status': status})
                curr += timedelta(days=1)
            
            # (2) 단어 시험
            for _ in range(5):
                TestResult.objects.create(
                    student=student, book=word_book, score=random.randint(15, 30), total_count=30,
                    created_at=timezone.now() - timedelta(days=random.randint(0, 20))
                )

            # (3) 수업 일지 (수정됨: textbook_progress 제거)
            for i in range(3):
                # ClassLog 모델 필드에 맞춰 수정
                log = ClassLog.objects.create(
                    student=student, 
                    teacher=teacher_user, 
                    date=today - timedelta(days=i*5),
                    subject='SYNTAX' if i%2==0 else 'READING',
                    # textbook_progress 필드 제거 (오류 원인)
                    # 대신 comment에 내용을 합침
                    comment=f"[{syntax_book.title} {i+1}강 진도] " + fake.sentence()
                )
                # 만약 ClassLogEntry 모델이 있다면 여기서 추가해주어야 합니다.
                # 예: ClassLogEntry.objects.create(log=log, textbook=..., progress_range=...)

            # (4) 월말 평가
            paper = TestPaper.objects.create(
                student=student, title=f"{student.name} {month}월 월말평가", target_chapters="1~5강"
            )
            result = ExamResult.objects.create(student=student, paper=paper, score=random.randint(60, 100))
            
            sample_qs = list(Question.objects.all()[:10])
            for q in sample_qs:
                ExamResultDetail.objects.create(
                    result=result, question=q, is_correct=random.choice([True, False]),
                    student_answer="sample"
                )
        
        self.stdout.write(self.style.SUCCESS("✨ 모든 가상 데이터 생성이 완료되었습니다!"))