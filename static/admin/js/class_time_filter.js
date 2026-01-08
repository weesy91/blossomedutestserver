/* static/admin/js/class_time_filter.js (최종_v3: 마감체크 강화판) */

(function($) {
    /**
     * [설정] 과목별 필터링 규칙 및 선생님 필드 매핑
     */
    const FIELD_RULES = [
        { 
            suffix: 'syntax_class', 
            teacherSuffix: 'syntax_teacher', 
            keyword: '구문', 
            typeDependency: false,
            role: 'syntax' 
        },
        { 
            suffix: 'reading_class', 
            teacherSuffix: 'reading_teacher', 
            keyword: '독해', 
            typeDependency: false,
            role: 'reading'
        },
        { 
            suffix: 'extra_class', 
            teacherSuffix: 'extra_class_teacher', 
            keyword: '',     
            typeDependency: true, 
            role: 'extra'
        }
    ];

    $(document).ready(function() {
        console.log("🚀 [Final] 시간표 필터 + 중복 마감 체크 스크립트 시작");

        // 1. 페이지 로드 시 모든 행 초기화
        $('select[name$="-branch"]').each(function() {
            initializeRow($(this));
        });

        // 2. 행 추가 시 초기화 (Inline)
        $(document).on('formset:added', function(event, $row, formsetName) {
            $row.find('select[name$="-branch"]').each(function() {
                initializeRow($(this));
            });
        });
    });

    function initializeRow($branchSelect) {
        const branchId = $branchSelect.attr('id'); 
        if (!branchId) return;

        // ID에서 prefix 추출 (예: id_studentprofile_set-0)
        const prefix = branchId.substring(0, branchId.lastIndexOf('-'));
        
        const targets = [];

        FIELD_RULES.forEach(function(rule) {
            // 시간표 박스와 선생님 박스 찾기
            const $select = $('#' + prefix + '-' + rule.suffix);
            const $teacherSelect = $('#' + prefix + '-' + rule.teacherSuffix);

            if ($select.length > 0) {
                // (1) 요일 필터 생성
                createDayFilter($select);

                // (2) 타겟 정보 객체 생성
                const targetObj = {
                    $el: $select,           // 시간표 Element
                    $teacherEl: $teacherSelect, // 선생님 Element
                    keyword: rule.keyword,
                    rule: rule,
                    prefix: prefix
                };
                
                // (3) 선생님 변경 시 -> 마감 체크 즉시 실행
                if ($teacherSelect.length > 0) {
                    $teacherSelect.on('change', function() {
                        console.log(`👨‍🏫 선생님 변경됨 (${rule.role}) -> 마감 체크 실행`);
                        checkOccupancy(targetObj);
                    });
                } else {
                    console.warn(`⚠️ 선생님 선택 박스를 찾을 수 없음: #${prefix}-${rule.teacherSuffix}`);
                }

                // (4) 추가수업 타입 변경 시 -> 리렌더링
                if (rule.typeDependency) {
                    const $typeSelect = $('#' + prefix + '-extra_class_type');
                    if ($typeSelect.length > 0) {
                        targetObj.$typeEl = $typeSelect;
                        $typeSelect.on('change', function() {
                            renderOptions(targetObj); 
                        });
                    }
                }

                targets.push(targetObj);

                // (5) [수정 모드 진입 시]
                // 현재 HTML에 박혀있는 옵션들을 '원본'으로 저장하고, 마감 체크 한번 돌림
                if ($select.find('option').length > 1) {
                    $select.data('master-options', $select.find('option').clone());
                    // 0.5초 딜레이 후 체크 (브라우저 렌더링 안정화)
                    setTimeout(function() {
                        checkOccupancy(targetObj);
                    }, 500);
                }
            }
        });

        // 3. 지점 변경 이벤트 연결
        $branchSelect.off('change.classTimeFilter').on('change.classTimeFilter', function() {
            updateClassTimes($(this).val(), targets);
        });
        
        // 4. [수정 모드 초기화]
        // 페이지 로드 시점에 이미 지점이 선택되어 있다면, 시간표를 서버에서 다시 가져와서 깨끗하게 세팅
        if ($branchSelect.val()) {
            // console.log("🔄 수정 모드: 시간표 데이터 갱신 요청");
            updateClassTimes($branchSelect.val(), targets);
        }
    }

    // [UI] 요일 필터 생성
    function createDayFilter($select) {
        if ($select.prev('.day-filter-box').length > 0) return;

        const $dayFilter = $('<select class="day-filter-box" style="margin-right:5px; width:90px;">')
            .append('<option value="">📅 요일</option>')
            .append('<option value="월요일">월요일</option>')
            .append('<option value="화요일">화요일</option>')
            .append('<option value="수요일">수요일</option>')
            .append('<option value="목요일">목요일</option>')
            .append('<option value="금요일">금요일</option>')
            .append('<option value="토요일">토요일</option>')
            .append('<option value="일요일">일요일</option>');

        $select.before($dayFilter);

        $dayFilter.on('change', function() {
            // 요일 필터 바로 뒤에 있는 select 박스(시간표)를 찾음
            const $relatedSelect = $(this).next('select');
            
            // DOM Traverse로 targetObj 없이 필터링 수행
            applyDayFilterDOM($relatedSelect, $(this).val());
        });
    }

    // [AJAX] 서버에서 시간표 가져오기
    function updateClassTimes(branchId, targets) {
        if (!branchId) {
            targets.forEach(t => {
                t.$el.html('<option value="">---------</option>');
                t.$el.data('master-options', null);
                t.$el.prev('.day-filter-box').val('');
            });
            return;
        }

        $.ajax({
            url: '/core/api/get-classtimes/',
            data: { 'branch_id': branchId },
            success: function(data) {
                targets.forEach(function(target) {
                    // 1. 키워드 필터링 (구문/독해)
                    let filteredHtml = '<option value="">---------</option>';
                    $.each(data, function(idx, item) {
                        if (target.keyword === "" || item.name.indexOf(target.keyword) !== -1) {
                            filteredHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                        }
                    });

                    // 2. Master Data 저장
                    const $newOptions = $(filteredHtml);
                    target.$el.data('master-options', $newOptions); 
                    
                    // 3. 화면 그리기 & 마감 체크
                    renderOptions(target);
                    
                    // 4. 요일 필터 초기화
                    target.$el.prev('.day-filter-box').val('');
                });
            },
            error: function(err) {
                console.error("❌ 시간표 불러오기 실패:", err);
            }
        });
    }

    // [렌더링] 필터 적용 -> HTML 업데이트 -> 마감 체크 호출
    function renderOptions(target) {
        const $select = target.$el;
        const $master = $select.data('master-options');
        if (!$master) return;

        let $options = $master.clone();

        // (A) 추가수업 타입 필터
        if (target.rule.typeDependency && target.$typeEl) {
            const typeVal = target.$typeEl.val(); 
            if (typeVal === 'SYNTAX') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('구문') !== -1);
            } else if (typeVal === 'READING') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('독해') !== -1);
            }
        }

        // (B) 요일 필터
        const $dayFilter = $select.prev('.day-filter-box');
        if ($dayFilter.length > 0) {
            const dayVal = $dayFilter.val();
            if (dayVal) {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf(dayVal) !== -1);
            }
        }

        // (C) DOM 업데이트
        const currentVal = $select.val();
        $select.empty().append($options);
        if (currentVal) $select.val(currentVal);

        // (D) ✅ 마감 체크 실행 (렌더링 직후)
        checkOccupancy(target);
    }

    // [Helper] 요일 필터 변경 시 DOM 기반 필터링 & 마감 체크 트리거
    function applyDayFilterDOM($select, dayVal) {
        const $master = $select.data('master-options');
        if (!$master) return;

        let $options = $master.clone();
        
        // 추가수업 타입 필터 (DOM에서 찾기)
        const nameAttr = $select.attr('name');
        if (nameAttr && nameAttr.indexOf('extra_class') !== -1) {
            const prefix = $select.attr('id').replace('-extra_class', '');
            const $typeEl = $('#' + prefix + '-extra_class_type');
            if ($typeEl.length > 0) {
                const typeVal = $typeEl.val();
                if (typeVal === 'SYNTAX') {
                    $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('구문') !== -1);
                } else if (typeVal === 'READING') {
                    $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('독해') !== -1);
                }
            }
        }

        if (dayVal) {
            $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf(dayVal) !== -1);
        }

        const currentVal = $select.val();
        $select.empty().append($options);
        if (currentVal) $select.val(currentVal);

        // 필터링 후 마감 체크를 위해 이벤트 발생 (Teacher ID를 찾아서 넘김)
        const selectId = $select.attr('id'); // 예: id_...-syntax_class
        const prefix = selectId.substring(0, selectId.lastIndexOf('-'));
        
        let teacherSuffix = '';
        let role = '';
        if (nameAttr.includes('syntax')) { teacherSuffix = 'syntax_teacher'; role = 'syntax'; }
        else if (nameAttr.includes('reading')) { teacherSuffix = 'reading_teacher'; role = 'reading'; }
        else if (nameAttr.includes('extra')) { teacherSuffix = 'extra_class_teacher'; role = 'extra'; }

        const $teacherSelect = $('#' + prefix + '-' + teacherSuffix);
        
        // 약식 타겟 객체로 체크 실행
        checkOccupancy({
            $el: $select,
            $teacherEl: $teacherSelect,
            rule: { role: role }
        });
    }

    // [핵심] API 호출하여 중복/마감된 시간표 비활성화
    function checkOccupancy(target) {
        const $teacher = target.$teacherEl;
        const $classTime = target.$el;
        
        if (!$teacher || $teacher.length === 0) {
            // console.log("⚠️ checkOccupancy: 선생님 필드를 찾을 수 없음");
            return;
        }

        const teacherId = $teacher.val();
        if (!teacherId) {
            // 선생님 미선택 시 -> 마감 표시 제거 & 활성화
            $classTime.find('option').prop('disabled', false).each(function() {
                $(this).text($(this).text().replace(' ⛔(마감)', ''));
            });
            return;
        }

        // 현재 페이지 URL에서 학생 ID 추출 (자기 자신 중복 허용)
        const urlMatch = window.location.pathname.match(/studentuser\/(\d+)\/change/);
        const currentStudentId = urlMatch ? urlMatch[1] : null;

        // API 호출
        $.ajax({
            url: '/academy/api/admin/teacher-schedule/',
            data: {
                'teacher_id': teacherId,
                'subject': target.rule.role,
                'current_student_id': currentStudentId
            },
            success: function(response) {
                const occupiedIds = response.occupied_ids; // [1, 5, 10] 형태의 숫자 배열
                const currentVal = parseInt($classTime.val());

                // console.log(`🔍 [${target.rule.role}] 마감 ID 목록:`, occupiedIds);

                $classTime.find('option').each(function() {
                    const optVal = parseInt($(this).val()); // 문자열 "1" -> 숫자 1
                    if (isNaN(optVal)) return;

                    // 텍스트에서 (마감) 글자 일단 제거 (중복 누적 방지)
                    let text = $(this).text().replace(' ⛔(마감)', '');

                    // 포함 여부 확인
                    const isOccupied = occupiedIds.includes(optVal);
                    // 현재 선택된 값은 마감이어도 비활성화하지 않음 (수정 가능하도록)
                    const isSelected = (optVal === currentVal);

                    if (isOccupied && !isSelected) {
                        $(this).prop('disabled', true);
                        $(this).css({ 'color': '#cccccc', 'font-style': 'italic' });
                        $(this).text(text + ' ⛔(마감)');
                    } else {
                        $(this).prop('disabled', false);
                        $(this).css({ 'color': '', 'font-style': '' });
                        $(this).text(text);
                    }
                });
            },
            error: function(xhr) {
                console.error("API Error checking occupancy:", xhr.responseText);
            }
        });
    }

})(django.jQuery);