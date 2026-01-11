import json
import random, datetime, calendar
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Avg, Q, Max, Count, Sum
from django.db.models.functions import TruncDate 

from .models import WordBook, Word, TestResult, TestResultDetail, MonthlyTestResult, MonthlyTestResultDetail, Publisher, RankingEvent, PersonalWrongWord
from core.models import StudentProfile

# 분리한 파일들 가져오기
from . import utils
from . import services

def is_monthly_test_period():
     now = timezone.now()
     last_day = calendar.monthrange(now.year, now.month)[1]
     # 매달 마지막 8일간을 월말평가 기간으로 설정
     return now.day > (last_day - 8)

# ==========================================
# [View] 메인 화면
# ==========================================
@login_required(login_url='core:login')
def index(request):
    if not hasattr(request.user, 'profile'):
        return render(request, 'vocab/index.html', {'error': '학생 프로필이 없습니다.'})
    
    profile = request.user.profile
    
    # [수정] '시스템' 출판사 제외
    publishers = Publisher.objects.exclude(name='시스템').order_by('name')
    etc_books = WordBook.objects.filter(publisher__isnull=True).order_by('-created_at')
    
    wrong_words = utils.get_vulnerable_words(profile)
    recent_tests = TestResult.objects.filter(student=profile).order_by('-created_at')[:10]
    graph_labels = [t.created_at.strftime('%m/%d') for t in reversed(recent_tests)]
    graph_data = [t.score for t in reversed(recent_tests)]

    # 1. 히트맵(잔디 심기) 데이터 생성
    one_year_ago = timezone.now() - timedelta(days=365)
    heatmap_qs = TestResult.objects.filter(
        student=profile,
        created_at__gte=one_year_ago
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    heatmap_data = {}
    for item in heatmap_qs:
        dt = datetime.datetime.combine(item['date'], datetime.datetime.min.time())
        timestamp = int(dt.timestamp())
        heatmap_data[timestamp] = item['count']

    # 2. 랭킹 시스템
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # (A) 이달의 랭킹
    total_ranks = TestResult.objects.filter(
        created_at__gte=start_of_month,
        score__gte=27
    ).values('student__name', 'student__school__name', 'student__user__username') \
     .annotate(total_score=Sum('score')) \
     .order_by('-total_score')[:5]

    monthly_ranking = []
    for i, r in enumerate(total_ranks, 1):
        name = r['student__name'] or r['student__user__username']
        school = r['student__school__name'] or ""
        display_name = f"{name} ({school})" if school else name
        monthly_ranking.append({'rank': i, 'name': display_name, 'score': r['total_score']})

    # (B) 이벤트 랭킹
    event_list = [] 
    active_events = RankingEvent.objects.filter(
        Q(branch=profile.branch) | Q(branch__isnull=True), 
        is_active=True
    ).order_by('-start_date')
    
    for event in active_events:
        event_ranks = TestResult.objects.filter(
            book=event.target_book,
            created_at__date__gte=event.start_date,
            created_at__date__lte=event.end_date,
            score__gte=27
        ).values('student__name', 'student__school__name', 'student__user__username') \
         .annotate(event_score=Sum('score')) \
         .order_by('-event_score')[:5]

        ranking_data = []
        for i, r in enumerate(event_ranks, 1):
            name = r['student__name'] or r['student__user__username']
            school = r['student__school__name'] or ""
            display_name = f"{name} ({school})" if school else name
            ranking_data.append({'rank': i, 'name': display_name, 'score': r['event_score']})
            
        event_list.append({'info': event, 'rankings': ranking_data})

    return render(request, 'vocab/index.html', {
        'publishers': publishers,
        'etc_books': etc_books,
        'is_monthly_period': is_monthly_test_period(),
        'is_wrong_mode_active': len(wrong_words) >= 30, 
        'wrong_count': len(wrong_words),
        'graph_labels': json.dumps(graph_labels),
        'graph_data': json.dumps(graph_data),
        'heatmap_data': json.dumps(heatmap_data),
        'monthly_ranking': monthly_ranking,
        'event_list': event_list,
    })


# ==========================================
# [View] 시험 페이지 (Exam)
# ==========================================
@login_required(login_url='core:login')
def exam(request):
    if not hasattr(request.user, 'profile'):
        return redirect('vocab:index')
    
    profile = request.user.profile
    mode = request.GET.get('mode', 'practice')
    
    is_monthly = (mode == 'monthly')
    is_challenge = (mode == 'challenge')
    is_wrong_mode = (mode == 'wrong')
    is_practice = (mode == 'practice')
    is_learning = (mode == 'learning')

    if is_monthly:
        now = timezone.now()
        if MonthlyTestResult.objects.filter(student=profile, created_at__year=now.year, created_at__month=now.month).exists():
            return HttpResponse(f"<script>alert('🚫 월말평가는 이번 달에 이미 응시하셨습니다.');window.location.href='/vocab/';</script>")

    # 쿨타임 체크
    if is_challenge:
        if profile.last_failed_at:
            time_passed = timezone.now() - profile.last_failed_at
            if time_passed < timedelta(minutes=5):
                remaining = 5 - (time_passed.seconds // 60)
                return HttpResponse(f"<script>alert('🔥 쿨타임 중입니다. ({remaining}분 남음)');window.location.href='/vocab/';</script>")
    elif is_wrong_mode:
        if profile.last_wrong_failed_at:
            time_passed = timezone.now() - profile.last_wrong_failed_at
            if time_passed < timedelta(minutes=5):
                remaining = 5 - (time_passed.seconds // 60)
                return HttpResponse(f"<script>alert('🚨 오답모드 쿨타임 중입니다. ({remaining}분 남음)');window.location.href='/vocab/';</script>")

    raw_candidates = []
    book_title = ""
    book_id = request.GET.get('book_id')

    if is_wrong_mode:
        raw_candidates = utils.get_vulnerable_words(profile)
        if len(raw_candidates) < 1: return redirect('vocab:index') 
        book_title = "🚨 오답 탈출"
    elif book_id:
        book = get_object_or_404(WordBook, id=book_id)
        book_title = book.title
        if is_monthly: book_title = f"[월말] {book_title}"

        test_range = request.GET.get('day_range', '전체')
        
        if test_range != '전체':
            try:
                targets = []
                for chunk in test_range.split(','):
                    if '-' in chunk:
                        s, e = map(int, chunk.split('-'))
                        targets.extend(range(s, e + 1))
                    else:
                        targets.append(int(chunk))
                raw_candidates = list(Word.objects.filter(book=book, number__in=targets))
            except:
                raw_candidates = list(Word.objects.filter(book=book))
        else:
            raw_candidates = list(Word.objects.filter(book=book))
            
    elif is_monthly:
        raw_candidates = list(Word.objects.all())
        book_title = "📅 전체 월말 평가"
    else:
        return redirect('vocab:index')

    # [셔플 및 자르기]
    if is_learning:
        raw_candidates.sort(key=lambda x: x.number)
        target_count = 999999
    else:
        if not is_wrong_mode: 
            random.shuffle(raw_candidates)
        target_count = 30
        if is_monthly: target_count = 100
        elif is_practice: target_count = 999999

    words = []
    seen = set()
    for w in raw_candidates:
        clean_eng = w.english.strip().lower()
        if clean_eng not in seen:
            words.append(w)
            seen.add(clean_eng)
        if len(words) >= target_count: break

    if is_challenge and len(words) < 25:
        return HttpResponse(f"""
            <script>
                alert('🚫 단어 수가 부족합니다.\\n도전모드는 최소 30단어 이상이어야 응시 가능합니다.\\n(현재 선택된 범위: {len(words)}단어)');
                window.history.back();
            </script>
        """)

    pre_saved_id = None
    if not is_practice and not is_learning:
        if is_monthly:
            result = MonthlyTestResult.objects.create(
                student=profile, 
                book=WordBook.objects.first() if not book_id else WordBook.objects.get(id=book_id),
                score=0, 
                test_range=request.GET.get('day_range', '전체')
            )
        else:
            current_book = WordBook.objects.first() if not book_id else WordBook.objects.get(id=book_id)
            
            # [수정] 오답모드일 경우 '오답 집중 공략' 전용 단어장 연결
            if is_wrong_mode: 
                system_user = User.objects.filter(is_superuser=True).first()
                if not system_user: system_user = request.user
                sys_pub, _ = Publisher.objects.get_or_create(name="시스템")
                current_book, _ = WordBook.objects.get_or_create(
                    title="🚨 오답 집중 공략",
                    publisher=sys_pub,
                    defaults={'uploaded_by': system_user}
                )

            result = TestResult.objects.create(
                student=profile, 
                book=current_book, 
                score=0, 
                wrong_count=len(words),
                test_range="오답집중" if is_wrong_mode else request.GET.get('day_range', '전체')
            )
            services.update_cooldown(profile, mode, 0) 
            
        pre_saved_id = result.id

    word_list = [{'english': w.english, 'korean': w.korean, 'example': w.example_sentence or "", 'day': w.number} for w in words]

    return render(request, 'vocab/exam.html', {
        'words_json': word_list,
        'mode': mode,
        'book_title': book_title,
        'test_id': pre_saved_id,
        'is_practice': is_practice,
        'is_monthly': is_monthly,
        'is_wrong_mode': is_wrong_mode,
        'is_learning': is_learning,
    })

# ==========================================
# [API] 결과 저장
# ==========================================
@csrf_exempt
def save_result(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mode = data.get('mode')
            if mode in ['practice', 'learning']: 
                return JsonResponse({'status': 'success'})
            
            if not hasattr(request.user, 'profile'):
                return JsonResponse({'status': 'error', 'message': '프로필 없음'})
            profile = request.user.profile

            test_id = data.get('test_id')
            is_monthly = (mode == 'monthly')
            
            raw_details = data.get('details', [])
            
            if is_monthly:
                result_obj = get_object_or_404(MonthlyTestResult, id=test_id, student=profile)
            else:
                result_obj = get_object_or_404(TestResult, id=test_id, student=profile)
            
            # DB 진짜 정답 조회
            real_answers = {
                w.english: w.korean 
                for w in Word.objects.filter(book=result_obj.book)
            }
            
            for item in raw_details:
                question = item.get('english') or item.get('q')
                if question in real_answers:
                    item['korean'] = real_answers[question]
                    item['a'] = real_answers[question]

            score, wrong_count, processed_details = services.calculate_score(raw_details)

            detail_ids = []

            with transaction.atomic():
                if is_monthly:
                    if MonthlyTestResultDetail.objects.filter(result=result_obj).exists():
                         saved_objs = MonthlyTestResultDetail.objects.filter(result=result_obj).order_by('id')
                         detail_ids = [d.id for d in saved_objs]
                         return JsonResponse({'status': 'success', 'message': 'Duplicate skipped', 'detail_ids': detail_ids})
                    
                    result_obj.score = score
                    result_obj.save()
                    ModelDetail = MonthlyTestResultDetail
                else:
                    if TestResultDetail.objects.filter(result=result_obj).exists():
                        saved_objs = TestResultDetail.objects.filter(result=result_obj).order_by('id')
                        detail_ids = [d.id for d in saved_objs]
                        return JsonResponse({'status': 'success', 'message': 'Duplicate skipped', 'detail_ids': detail_ids})

                    result_obj.score = score
                    result_obj.wrong_count = wrong_count
                    result_obj.save()
                    ModelDetail = TestResultDetail
                    
                    services.update_cooldown(profile, mode, score)

                details = [
                    ModelDetail(
                        result=result_obj, 
                        word_question=item['q'], 
                        student_answer=item['u'], 
                        correct_answer=item['a'], 
                        is_correct=item['c']
                    ) 
                    for item in processed_details
                ]
                ModelDetail.objects.bulk_create(details)

                saved_objs = ModelDetail.objects.filter(result=result_obj).order_by('id')
                detail_ids = [d.id for d in saved_objs]
            
            return JsonResponse({'status': 'success', 'detail_ids': detail_ids})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

# ==========================================
# [API] 정답 인정 (관리자용)
# ==========================================
@csrf_exempt
@login_required
def approve_answer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            detail_id = data.get('detail_id')
            is_monthly_detail = False
            
            try: 
                detail = TestResultDetail.objects.select_for_update().get(id=detail_id)
            except TestResultDetail.DoesNotExist:
                try: 
                    detail = MonthlyTestResultDetail.objects.select_for_update().get(id=detail_id)
                    is_monthly_detail = True
                except: 
                    return JsonResponse({'status': 'error', 'message': '존재하지 않는 답안 ID'})

            with transaction.atomic():
                if detail.is_correct: 
                    return JsonResponse({'status': 'already_correct'})
                
                detail.is_correct = True
                detail.is_resolved = True
                detail.save()
                
                result = detail.result
                if is_monthly_detail:
                    result = MonthlyTestResult.objects.select_for_update().get(id=result.id)
                    new_score = MonthlyTestResultDetail.objects.filter(result=result, is_correct=True).count()
                    result.score = new_score
                    result.save()
                else:
                    result = TestResult.objects.select_for_update().get(id=result.id)
                    new_score = TestResultDetail.objects.filter(result=result, is_correct=True).count()
                    total_count = TestResultDetail.objects.filter(result=result).count()
                    result.score = new_score
                    result.wrong_count = total_count - new_score
                    result.save()
                    
                    mode = 'wrong' if result.test_range == '오답집중' else 'challenge'
                    try:
                        services.update_cooldown(result.student, mode, result.score, result.test_range)
                    except:
                        pass 

            return JsonResponse({'status': 'success', 'new_score': result.score})
            
        except Exception as e: 
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error'})

@login_required
def wrong_answer_study(request):
    if not hasattr(request.user, 'profile'): return redirect('vocab:index')
    profile = request.user.profile
    vulnerable_words = utils.get_vulnerable_words(profile)
    return render(request, 'vocab/wrong_study.html', {'words': vulnerable_words, 'count': len(vulnerable_words)})

@csrf_exempt
@login_required
def request_correction(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # [수정] detail_id와 is_monthly 가져오기
            detail_id = data.get('detail_id')
            is_monthly = data.get('is_monthly', False)

            if is_monthly: detail = get_object_or_404(MonthlyTestResultDetail, id=detail_id)
            else: detail = get_object_or_404(TestResultDetail, id=detail_id)

            if not hasattr(request.user, 'profile') or detail.result.student != request.user.profile:
                return JsonResponse({'status': 'error', 'message': '권한 없음'})

            if detail.is_correct:
                return JsonResponse({'status': 'error', 'message': '이미 정답 처리된 문제입니다. 👍'})

            detail.is_correction_requested = True
            detail.is_resolved = False
            detail.save()
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

@login_required
def test_result_list(request):
    if not request.user.is_staff: return redirect('vocab:index')
    results = TestResult.objects.all().order_by('-created_at')
    return render(request, 'vocab/admin_result_list.html', {'results': results})

@login_required
def test_result_detail(request, result_id):
    result = get_object_or_404(TestResult, id=result_id)
    try: details = result.details.all().order_by('id')
    except AttributeError: details = result.testresultdetail_set.all().order_by('id')
    return render(request, 'vocab/admin_result_detail.html', {'result': result, 'details': details})

@staff_member_required
def admin_event_check(request):
    today = timezone.now().date()
    start_date = today - timedelta(days=29)
    pass_records = TestResult.objects.filter(
        created_at__date__gte=start_date, score__gte=27
    ).annotate(exam_date=TruncDate('created_at')).values(
        'student__user__id', 'student__user__username', 'student__name', 'exam_date'
    ).distinct()
    
    student_stats = {}
    for record in pass_records:
        uid = record['student__user__id']
        name = record['student__name'] 
        if not name: name = record['student__user__username']
        if uid not in student_stats: student_stats[uid] = {'name': name, 'days': 0}
        student_stats[uid]['days'] += 1
    
    result_list = [{'name': v['name'], 'days': v['days'], 'success_rate': round((v['days']/30)*100, 1)} for v in student_stats.values()]
    result_list.sort(key=lambda x: x['days'], reverse=True)
    return render(request, 'vocab/admin_event_check.html', {'challengers': result_list, 'total_days': 30})

@staff_member_required
def grading_list(request):
    sort_by = request.GET.get('sort', 'date')
    user = request.user
    staff_profile = getattr(user, 'staff_profile', None)
    position = staff_profile.position if staff_profile else None
    my_assign_condition = Q(syntax_teacher=user) | Q(reading_teacher=user) | Q(extra_class_teacher=user)
    
    stats_qs = StudentProfile.objects.none() 
    pending_filter = Q(pk__in=[])            

    if position == 'TA':
        stats_qs = StudentProfile.objects.all()
        pending_filter = Q() 
    elif position == 'PRINCIPAL':
        if staff_profile and staff_profile.branch:
            pending_filter = Q(student__branch=staff_profile.branch)
        stats_qs = StudentProfile.objects.filter(my_assign_condition).distinct()
    else:
        stats_qs = StudentProfile.objects.filter(my_assign_condition).distinct()
        pending_filter = (
            Q(student__syntax_teacher=user) | 
            Q(student__reading_teacher=user) | 
            Q(student__extra_class_teacher=user)
        )

    pending_tests = TestResult.objects.filter(
        details__is_correction_requested=True, 
        details__is_resolved=False
    ).filter(pending_filter).distinct().select_related('student', 'book')

    pending_monthly = MonthlyTestResult.objects.filter(
        details__is_correction_requested=True, 
        details__is_resolved=False
    ).filter(pending_filter).distinct().select_related('student', 'book')

    exam_list = []
    def add_to_list(queryset, q_type):
        for exam in queryset:
            req_count = exam.details.filter(is_correction_requested=True, is_resolved=False).count()
            exam_list.append({
                'id': exam.id, 'type': q_type, 
                'student_name': exam.student.name,
                'book_title': exam.book.title, 
                'test_range': exam.test_range,
                'score': exam.score, 
                'pending_count': req_count, 
                'created_at': exam.created_at
            })
    add_to_list(pending_tests, 'normal')
    add_to_list(pending_monthly, 'monthly')
    
    if sort_by == 'name': exam_list.sort(key=lambda x: x['student_name'])
    else: exam_list.sort(key=lambda x: x['created_at'], reverse=True)

    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0)
    stats_qs = stats_qs.annotate(
        last_passed_dt=Max(
            'test_results__created_at',
            filter=Q(test_results__score__gte=27)
        )
    )

    student_stats = []
    for student in stats_qs:
        month_count = TestResult.objects.filter(student=student, created_at__gte=start_of_month).count()
        last_date = student.last_passed_dt
        days_since = 999 
        if last_date:
            diff = now - last_date
            days_since = diff.days
            
        status = 'GOOD'
        if last_date is None: status = 'NONE'
        elif days_since >= 6: status = 'DANGER'
        elif days_since >= 4: status = 'WARNING'
        elif days_since >= 2: status = 'CAUTION'
        
        student_stats.append({
            'id': student.id,
            'name': student.name,
            'school': student.school.name if student.school else "",
            'last_test_date': last_date, 
            'days_since': days_since,
            'month_count': month_count,
            'status': status
        })
    student_stats.sort(key=lambda x: (x['status'] == 'NONE', -x['days_since']), reverse=True)

    context = {
        'exam_list': exam_list,
        'current_sort': sort_by,
        'student_stats': student_stats,
        'pending_total': len(exam_list)
    }
    return render(request, 'vocab/grading_list.html', context)

@staff_member_required
def grading_detail(request, test_type, result_id):
    if test_type == 'monthly': exam = get_object_or_404(MonthlyTestResult, id=result_id)
    else: exam = get_object_or_404(TestResult, id=result_id)
    details = exam.details.all().order_by('id')
    student_name = exam.student.name 
    return render(request, 'vocab/grading_detail.html', {'exam': exam, 'details': details, 'test_type': test_type, 'student_name': student_name})

@csrf_exempt
@login_required
def reject_answer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            detail_id = data.get('detail_id')
            q_type = data.get('type')
            if q_type == 'monthly': detail = get_object_or_404(MonthlyTestResultDetail, id=detail_id)
            else: detail = get_object_or_404(TestResultDetail, id=detail_id)
            detail.is_resolved = True; detail.is_correction_requested = False; detail.save()
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

@staff_member_required
def api_check_grading_status(request):
    user = request.user
    staff_profile = getattr(user, 'staff_profile', None)
    position = staff_profile.position if staff_profile else None
    qs_normal = TestResultDetail.objects.filter(is_correction_requested=True, is_resolved=False)
    qs_monthly = MonthlyTestResultDetail.objects.filter(is_correction_requested=True, is_resolved=False)

    if position == 'TA': pass 
    elif position == 'PRINCIPAL':
        if staff_profile and staff_profile.branch:
            qs_normal = qs_normal.filter(result__student__branch=staff_profile.branch)
            qs_monthly = qs_monthly.filter(result__student__branch=staff_profile.branch)
        else:
            qs_normal = qs_normal.none(); qs_monthly = qs_monthly.none()
    else:
        my_student_filter = (
            Q(result__student__syntax_teacher=user) | 
            Q(result__student__reading_teacher=user) |
            Q(result__student__extra_class_teacher=user)
        )
        qs_normal = qs_normal.filter(my_student_filter)
        qs_monthly = qs_monthly.filter(my_student_filter)
    
    total_pending = qs_normal.count() + qs_monthly.count()
    return JsonResponse({'status': 'success', 'pending_count': total_pending})

@login_required
def search_word_page(request):
    return render(request, 'vocab/search_word.html')

@login_required
def api_search_word(request):
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'results': []})
    results = []
    
    db_words = Word.objects.filter(english__icontains=query).select_related('book')[:5]
    for w in db_words:
        results.append({
            'id': w.id,
            'english': w.english,
            'korean': w.korean,
            'book_title': w.book.title,
            'book_publisher': w.book.publisher.name if w.book.publisher else "기타",
            'is_db': True 
        })
        
    if not any(r['english'].lower() == query.lower() for r in results):
        external_word = utils.crawl_daum_dic(query) 
        if external_word:
            if not any(r['english'] == external_word['english'] for r in results):
                results.append({
                    'id': None, 
                    'english': external_word['english'],
                    'korean': external_word['korean'],
                    'book_title': "인터넷 사전 검색",
                    'book_publisher': "Google", 
                    'is_db': False
                })
    return JsonResponse({'results': results})

@csrf_exempt
@login_required
def api_add_personal_wrong(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            profile = request.user.profile
            word = None

            if 'word_id' in data and data['word_id']:
                word = get_object_or_404(Word, id=data['word_id'])
            elif 'english' in data and 'korean' in data:
                english = data['english'].strip(); korean = data['korean'].strip()
                system_user = User.objects.filter(is_superuser=True).first()
                if not system_user: system_user = request.user 
                personal_pub, _ = Publisher.objects.get_or_create(name="개인단어장")
                ext_book, _ = WordBook.objects.get_or_create(
                    title="검색 단어장", publisher=personal_pub, uploaded_by=request.user
                )
                today_num = int(timezone.now().strftime('%m%d'))
                word, _ = Word.objects.get_or_create(
                    book=ext_book, english=english,
                    defaults={'korean': korean, 'number': today_num}
                )
            else: return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'})
            
            obj, created = PersonalWrongWord.objects.get_or_create(student=profile, word=word)
            if created: return JsonResponse({'status': 'success', 'message': f"'{word.english}' 추가 완료! 📝"})
            else: return JsonResponse({'status': 'info', 'message': '이미 오답 노트에 있는 단어입니다.'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

@login_required
def api_get_chapters(request):
    book_id = request.GET.get('book_id')
    if not book_id: return JsonResponse({'chapters': [], 'is_date_based': False})
    
    days = Word.objects.filter(book_id=book_id).values_list('number', flat=True).distinct().order_by('number')
    book = WordBook.objects.get(id=book_id)
    is_date_based = (book.publisher and book.publisher.name == "개인단어장")
    
    chapter_list = []
    for d in days:
        label = f"Day {d}"
        if is_date_based:
            month = d // 100; day = d % 100
            label = f"{month}월 {day}일"
        chapter_list.append({'value': d, 'label': label})
        
    return JsonResponse({'chapters': chapter_list, 'is_date_based': is_date_based})

@login_required
def api_date_history(request):
    date_str = request.GET.get('date')
    if not date_str: return JsonResponse({'status': 'error', 'message': 'Invalid request'})
    try: target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return JsonResponse({'status': 'error', 'message': 'Invalid date format'})

    if hasattr(request.user, 'profile'): profile = request.user.profile
    else: return JsonResponse({'status': 'error', 'message': 'No Profile'})
    
    results = TestResult.objects.filter(
        student=profile, created_at__date=target_date
    ).select_related('book').prefetch_related('details').order_by('-created_at')

    data = []
    for r in results:
        wrong_details = r.details.filter(is_correct=False)
        wrong_words = []
        for d in wrong_details:
            wrong_words.append({'word': d.word_question, 'answer': d.correct_answer})

        data.append({
            'time': r.created_at.strftime('%H:%M'),
            'book_title': r.book.title,
            'score': r.score,
            'total': r.score + r.wrong_count, 
            'wrong_words': wrong_words,
            'wrong_count': r.wrong_count
        })

    return JsonResponse({'status': 'success', 'date': date_str, 'exams': data})

@login_required
def wrong_word_list(request):
    if not hasattr(request.user, 'profile'): return redirect('vocab:index')
    profile = request.user.profile
    words = utils.get_vulnerable_words(profile)
    return render(request, 'vocab/wrong_list.html', {'words': words, 'count': len(words)})