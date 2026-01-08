/* static/admin/js/class_time_filter.js */

(function($) {
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
        console.log("🚀 [Final v4] 시간표 필터 + 안전한 중복체크 시작");

        // 1. 페이지 로드 시 모든 행 초기화
        $('select[name$="-branch"]').each(function() {
            initializeRow($(this));
        });

        // 2. 행 추가 시 초기화
        $(document).on('formset:added', function(event, $row, formsetName) {
            $row.find('select[name$="-branch"]').each(function() {
                initializeRow($(this));
            });
        });
    });

    function initializeRow($branchSelect) {
        const branchId = $branchSelect.attr('id'); 
        if (!branchId) return;

        const prefix = branchId.substring(0, branchId.lastIndexOf('-'));
        const targets = [];

        FIELD_RULES.forEach(function(rule) {
            const $select = $('#' + prefix + '-' + rule.suffix);
            const $teacherSelect = $('#' + prefix + '-' + rule.teacherSuffix);

            if ($select.length > 0) {
                // (1) 요일 필터 생성
                createDayFilter($select);

                // (2) 타겟 정보 저장
                const targetObj = {
                    $el: $select,
                    $teacherEl: $teacherSelect,
                    keyword: rule.keyword,
                    rule: rule,
                    prefix: prefix
                };
                
                // (3) 선생님 변경 시 -> 마감 체크
                if ($teacherSelect.length > 0) {
                    $teacherSelect.on('change', function() {
                        checkOccupancy(targetObj);
                    });
                }

                // (4) 추가수업 타입 연동
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

                // (5) 수정 페이지 진입 시: 원본 데이터 저장 & 즉시 마감 체크
                if ($select.find('option').length > 1) {
                    $select.data('master-options', $select.find('option').clone());
                    // 0.2초 딜레이로 렌더링 안정성 확보 후 체크
                    setTimeout(function() { checkOccupancy(targetObj); }, 200);
                }
            }
        });

        // 3. 지점 변경 이벤트
        $branchSelect.off('change.classTimeFilter').on('change.classTimeFilter', function() {
            updateClassTimes($(this).val(), targets);
        });
        
        // 4. (수정 모드) 지점이 선택되어 있으면 시간표 갱신
        if ($branchSelect.val()) {
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
            const $relatedSelect = $(this).next('select');
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
                    let filteredHtml = '<option value="">---------</option>';
                    $.each(data, function(idx, item) {
                        if (target.keyword === "" || item.name.indexOf(target.keyword) !== -1) {
                            filteredHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                        }
                    });

                    const $newOptions = $(filteredHtml);
                    target.$el.data('master-options', $newOptions); 
                    
                    renderOptions(target);
                    
                    target.$el.prev('.day-filter-box').val('');
                });
            },
            error: function(err) { console.error(err); }
        });
    }

    // [렌더링] 필터 적용 -> DOM 업데이트 -> 마감 체크
    function renderOptions(target) {
        const $select = target.$el;
        const $master = $select.data('master-options');
        if (!$master) return;

        let $options = $master.clone();

        // 타입 필터
        if (target.rule.typeDependency && target.$typeEl) {
            const typeVal = target.$typeEl.val(); 
            if (typeVal === 'SYNTAX') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('구문') !== -1);
            } else if (typeVal === 'READING') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('독해') !== -1);
            }
        }

        // 요일 필터
        const $dayFilter = $select.prev('.day-filter-box');
        if ($dayFilter.length > 0) {
            const dayVal = $dayFilter.val();
            if (dayVal) {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf(dayVal) !== -1);
            }
        }

        const currentVal = $select.val();
        $select.empty().append($options);
        if (currentVal) $select.val(currentVal);

        // ✅ 렌더링 직후 마감 체크 실행
        checkOccupancy(target);
    }

    // 요일 필터용 (DOM 기반)
    function applyDayFilterDOM($select, dayVal) {
        const $master = $select.data('master-options');
        if (!$master) return;

        let $options = $master.clone();
        
        // 타입 필터 (DOM 탐색)
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

        // 선생님 Element 찾아서 마감 체크 재호출
        const idParts = $select.attr('id').split('-'); // ['id_studentprofile_set', '0', 'syntax_class']
        const prefix = idParts.slice(0, -1).join('-');
        const suffix = idParts[idParts.length - 1]; // syntax_class

        let teacherSuffix = 'syntax_teacher';
        let role = 'syntax';
        if (suffix === 'reading_class') { teacherSuffix = 'reading_teacher'; role = 'reading'; }
        else if (suffix === 'extra_class') { teacherSuffix = 'extra_class_teacher'; role = 'extra'; }

        const $teacherSelect = $('#' + prefix + '-' + teacherSuffix);
        
        checkOccupancy({
            $el: $select,
            $teacherEl: $teacherSelect,
            rule: { role: role }
        });
    }

    // [핵심] API 호출 및 비활성화 (문자열 비교 방식 적용)
    function checkOccupancy(target) {
        const $teacher = target.$teacherEl;
        const $classTime = target.$el;
        
        if (!$teacher || $teacher.length === 0) return;

        const teacherId = $teacher.val();
        if (!teacherId) {
            $classTime.find('option').prop('disabled', false).each(function() {
                $(this).text($(this).text().replace(' ⛔(마감)', ''));
            });
            return;
        }

        const urlMatch = window.location.pathname.match(/studentuser\/(\d+)\/change/);
        const currentStudentId = urlMatch ? urlMatch[1] : null;

        $.ajax({
            url: '/academy/api/admin/teacher-schedule/',
            data: {
                'teacher_id': teacherId,
                'subject': target.rule.role,
                'current_student_id': currentStudentId
            },
            success: function(response) {
                // [중요] ID를 모두 문자열로 변환하여 안전하게 비교
                const occupiedIds = response.occupied_ids.map(String);
                const currentVal = String($classTime.val());

                console.log(`🔍 [${target.rule.role}] 마감된 시간표 IDs:`, occupiedIds);

                $classTime.find('option').each(function() {
                    const val = $(this).val();
                    if (!val) return; // 빈 값(placeholder) 제외

                    let text = $(this).text().replace(' ⛔(마감)', '');

                    // 문자열 기반 포함 여부 확인
                    const isOccupied = occupiedIds.includes(String(val));
                    const isSelected = (String(val) === currentVal);

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
            }
        });
    }

})(django.jQuery);