(function($) {
    /**
     * [설정] 과목별 필터링 규칙 정의
     * - suffix: 필드명 뒷부분 (예: syntax_class)
     * - keyword: 필터링할 단어 (예: '구문'). 이 단어가 수업명에 포함되어야 함.
     * - keyword가 빈 문자열('')이면 모든 수업을 표시함.
     */
    const FIELD_RULES = [
        { suffix: 'syntax_class', keyword: '구문' },   // 구문 수업
        { suffix: 'reading_class', keyword: '독해' },  // 독해 수업
        { suffix: 'extra_class', keyword: '' }         // 추가 수업 (전체 표시)
    ];

    $(document).ready(function() {
        console.log("🚀 시간표 필터 스크립트 로드됨 (지점+과목+요일)");

        // 1. 페이지 로드 시 존재하는 모든 '지점' 선택 박스에 대해 초기화 수행
        $('select[name$="-branch"]').each(function() {
            initializeRow($(this));
        });

        // 2. '학생 추가' 등으로 동적으로 행이 추가될 때도 초기화 수행
        $(document).on('formset:added', function(event, $row, formsetName) {
            $row.find('select[name$="-branch"]').each(function() {
                initializeRow($(this));
            });
        });
    });

    /**
     * 특정 '지점' 선택 박스가 있는 줄(Row)을 초기화하고 이벤트를 연결하는 함수
     */
    function initializeRow($branchSelect) {
        // ID 예시: id_profile-0-branch 또는 id_student_set-0-branch
        const branchId = $branchSelect.attr('id');
        if (!branchId) return;

        // prefix 추출 (예: "id_profile-0")
        const prefix = branchId.substring(0, branchId.lastIndexOf('-'));
        
        // 이 줄에서 제어해야 할 3개의 과목 선택 박스 찾기
        const targetSelects = [];

        FIELD_RULES.forEach(function(rule) {
            const selectId = prefix + '-' + rule.suffix;
            const $select = $('#' + selectId);
            
            if ($select.length > 0) {
                // (1) 각 과목 선택 박스 위에 '요일 필터' 생성
                createDayFilter($select);

                // (2) 추후 제어를 위해 배열에 저장
                targetSelects.push({
                    $el: $select,
                    keyword: rule.keyword
                });

                // (3) [중요] 페이지 로딩 시점(수정 화면)에 이미 데이터가 있다면
                // 그 데이터를 '요일 필터용 원본(Master Data)'으로 저장해둬야 함.
                if ($select.find('option').length > 1) {
                     $select.data('master-options', $select.find('option').clone());
                }
            }
        });

        // 3. '지점' 변경 시 이벤트 연결
        $branchSelect.off('change.classTimeFilter').on('change.classTimeFilter', function() {
            const selectedBranchId = $(this).val();
            updateClassTimes(selectedBranchId, targetSelects);
        });
    }

    /**
     * [UI] 요일 필터 생성 함수
     */
    function createDayFilter($targetSelect) {
        // 이미 생성되어 있다면 중복 생성 방지
        if ($targetSelect.prev('.day-filter-box').length > 0) return;

        // 요일 선택 박스 HTML
        const $dayFilter = $('<select class="day-filter-box" style="margin-right:8px; width:100px;">')
            .append('<option value="">📅 요일 (전체)</option>')
            .append('<option value="월요일">월요일</option>')
            .append('<option value="화요일">화요일</option>')
            .append('<option value="수요일">수요일</option>')
            .append('<option value="목요일">목요일</option>')
            .append('<option value="금요일">금요일</option>')
            .append('<option value="토요일">토요일</option>')
            .append('<option value="일요일">일요일</option>');

        // 시간표 박스 앞에 삽입
        $targetSelect.before($dayFilter);

        // 요일 변경 이벤트 핸들러
        $dayFilter.on('change', function() {
            const selectedDay = $(this).val();
            
            // [핵심] 저장해둔 '이 과목의 전체 목록(Master Options)'을 불러옴
            const $masterOptions = $targetSelect.data('master-options');
            
            if (!$masterOptions) return; // 데이터가 없으면 패스

            // 기존 목록 비우기
            $targetSelect.empty();

            // 마스터 목록을 순회하며 필터링
            $masterOptions.each(function() {
                const text = $(this).text();  // 예: "[월요일] 19:00 (구문)"
                const value = $(this).val();

                // (1) "---------" 빈 옵션이거나
                // (2) 요일을 선택하지 않았거나(전체 보기)
                // (3) 텍스트에 선택한 요일이 포함되어 있으면 -> 추가
                if (value === "" || selectedDay === "" || text.indexOf(selectedDay) !== -1) {
                    $targetSelect.append($(this).clone());
                }
            });
        });
    }

    /**
     * [AJAX] 지점 선택 시 서버에서 시간표를 가져와 과목별로 분배하는 함수
     */
    function updateClassTimes(branchId, targetSelects) {
        // 지점이 선택되지 않았다면 모든 칸 초기화
        if (!branchId) {
            targetSelects.forEach(function(target) {
                target.$el.html('<option value="">---------</option>');
                target.$el.data('master-options', null); // 원본 데이터 삭제
                target.$el.prev('.day-filter-box').val(''); // 요일 필터 초기화
            });
            return;
        }

        // 서버에 해당 지점의 시간표 요청
        $.ajax({
            url: '/core/api/get-classtimes/',
            data: { 'branch_id': branchId },
            success: function(data) {
                // data 예시: [{id: 1, name: "[월요일] 19:00 (구문 - 심화)"}, ...]

                // 각 과목 칸(구문/독해/추가)을 순회하며 데이터 채우기
                targetSelects.forEach(function(target) {
                    const $select = target.$el;
                    const keyword = target.keyword; // 예: '구문'

                    // (1) 데이터 분류: 해당 키워드가 포함된 수업만 골라내기
                    let filteredHtml = '<option value="">---------</option>';
                    
                    $.each(data, function(idx, item) {
                        // 키워드가 없거나(전체), 이름에 키워드가 포함되면 추가
                        if (keyword === "" || item.name.indexOf(keyword) !== -1) {
                            filteredHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                        }
                    });

                    // (2) DOM 업데이트
                    const $newOptions = $(filteredHtml);
                    
                    // (기존 선택값이 새 목록에도 있다면 유지하기 위한 로직)
                    const currentVal = $select.val();

                    $select.empty().append($newOptions);

                    // (3) [핵심] 요일 필터를 위해 '이 과목의 원본 데이터'로 저장
                    // -> 이렇게 해야 요일 필터를 껐다 켰다 할 때, 다른 과목 데이터가 섞이지 않음!
                    $select.data('master-options', $newOptions.clone());

                    // (4) 요일 필터 초기화 (새 지점이 선택됐으니 전체 보기로 리셋)
                    $select.prev('.day-filter-box').val('');

                    // (5) 값 복구 시도
                    if (currentVal) {
                        $select.val(currentVal);
                    }
                });
            },
            error: function(err) {
                console.error("시간표 불러오기 실패:", err);
                alert("시간표 데이터를 가져오는 데 실패했습니다.");
            }
        });
    }

})(django.jQuery);