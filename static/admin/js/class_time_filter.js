/* static/admin/js/class_time_filter.js */

(function($) {
    /**
     * [설정] 과목별 필터링 규칙
     * - keyword: 수업명에 이 단어가 포함되어야 함 (빈값이면 전체)
     * - typeDependency: 추가수업처럼 별도의 '타입 선택 박스'에 영향을 받는지 여부
     */
    const FIELD_RULES = [
        { suffix: 'syntax_class', keyword: '구문', typeDependency: false },
        { suffix: 'reading_class', keyword: '독해', typeDependency: false },
        { suffix: 'extra_class', keyword: '',     typeDependency: true } // 추가수업
    ];

    $(document).ready(function() {
        console.log("🚀 최종 통합 시간표 필터 (지점+타입+요일+중복검사연동)");

        // 1. 로드 시 모든 행 초기화
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
            if ($select.length > 0) {
                // (1) 요일 필터 생성
                createDayFilter($select);

                // (2) 타겟 정보 저장
                const targetObj = {
                    $el: $select,
                    keyword: rule.keyword,
                    rule: rule
                };
                
                // (3) '추가수업'인 경우 타입 박스 연동
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

                // (4) 수정 페이지 진입 시: 원본 저장
                if ($select.find('option').length > 1) {
                    $select.data('master-options', $select.find('option').clone());
                }
            }
        });

        // 3. 지점 변경 시 -> 서버에서 새 목록 받아오기
        $branchSelect.off('change.classTimeFilter').on('change.classTimeFilter', function() {
            updateClassTimes($(this).val(), targets);
        });
    }

    // [UI] 요일 필터 만들기
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

        // 요일 변경 시 -> 목록 다시 그리기
        $dayFilter.on('change', function() {
            applyFilters($select);
        });
    }

    // [AJAX] 데이터 가져오기
    function updateClassTimes(branchId, targets) {
        if (!branchId) {
            targets.forEach(t => {
                t.$el.html('<option value="">---------</option>');
                t.$el.data('master-options', null);
                t.$el.prev('.day-filter-box').val('');
                // 초기화 시에도 신호 보냄
                t.$el.trigger('options_refreshed'); 
            });
            return;
        }

        $.ajax({
            url: '/core/api/get-classtimes/',
            data: { 'branch_id': branchId },
            success: function(data) {
                targets.forEach(function(target) {
                    // 1. 키워드(구문/독해)로 1차 분류하여 'Master Data' 생성
                    let filteredHtml = '<option value="">---------</option>';
                    $.each(data, function(idx, item) {
                        if (target.keyword === "" || item.name.indexOf(target.keyword) !== -1) {
                            filteredHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                        }
                    });

                    // 2. Master Data 저장
                    const $newOptions = $(filteredHtml);
                    target.$el.data('master-options', $newOptions); 

                    // 3. 화면 렌더링
                    renderOptions(target);
                    
                    // 4. 요일 필터 초기화
                    target.$el.prev('.day-filter-box').val('');
                });
            }
        });
    }

    // [화면 그리기] Master Data -> 타입 필터 -> 요일 필터 -> DOM 적용
    function renderOptions(target) {
        const $select = target.$el;
        const $master = $select.data('master-options');
        if (!$master) return;

        // 1. Master 복제
        let $options = $master.clone();

        // 2. [필터 A] 추가수업 타입 (구문/독해) 필터링
        if (target.rule.typeDependency && target.$typeEl) {
            const typeVal = target.$typeEl.val(); 
            if (typeVal === 'SYNTAX') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('구문') !== -1);
            } else if (typeVal === 'READING') {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('독해') !== -1);
            }
        }

        // 3. [필터 B] 요일 필터링
        const $dayFilter = $select.prev('.day-filter-box');
        if ($dayFilter.length > 0) {
            const dayVal = $dayFilter.val();
            if (dayVal) {
                $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf(dayVal) !== -1);
            }
        }

        // 4. DOM 적용
        const currentVal = $select.val();
        $select.empty().append($options);
        if (currentVal) $select.val(currentVal);

        // ✅ [핵심 추가] 목록이 갱신되었으니 중복 검사 다시 하라고 신호 발사!
        $select.trigger('options_refreshed');
    }

    // 요일 필터 이벤트용 간소화 함수
    function applyFilters($select) {
        const $master = $select.data('master-options');
        if (!$master) return;

        let $options = $master.clone();
        
        // 1. 추가수업 타입 체크
        const nameAttr = $select.attr('name');
        if (nameAttr && nameAttr.indexOf('extra_class') !== -1) {
            const typeId = $select.attr('id').replace('extra_class', 'extra_class_type');
            const $typeEl = $('#' + typeId);
            
            if ($typeEl.length > 0) {
                const typeVal = $typeEl.val();
                if (typeVal === 'SYNTAX') {
                    $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('구문') !== -1);
                } else if (typeVal === 'READING') {
                    $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf('독해') !== -1);
                }
            }
        }

        // 2. 요일 체크
        const dayVal = $select.prev('.day-filter-box').val();
        if (dayVal) {
            $options = $options.filter((i, el) => el.value === "" || $(el).text().indexOf(dayVal) !== -1);
        }

        const currentVal = $select.val();
        $select.empty().append($options);
        if (currentVal) $select.val(currentVal);

        // ✅ [핵심 추가] 요일 바꿔서 목록 바뀌었으니 중복 검사 다시 해!
        $select.trigger('options_refreshed');
    }

})(django.jQuery);