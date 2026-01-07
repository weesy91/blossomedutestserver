/* static/admin/js/class_time_filter.js */

(function($) {
    $(document).ready(function() {
        console.log("🚀 시간표 필터(지점연동+과목분류+요일검색) 스크립트 시작!");

        var $branchSelect = $('select[name$="-branch"]');
        
        // 각 필드별로 어떤 글자가 포함된 수업을 보여줄지 설정
        const fieldFilters = {
            'syntax_class': '구문',   // 구문 필드엔 '구문' 수업만
            'reading_class': '독해',  // 독해 필드엔 '독해' 수업만
            'extra_class': ''         // 추가 수업은 모든 수업 표시 (필요시 수정 가능)
        };

        // 제어할 select 박스들을 저장할 객체
        var targetSelects = [];

        // 1. 초기화: 각 필드에 요일 필터 UI 붙이기
        Object.keys(fieldFilters).forEach(function(suffix) {
            const $select = $('select[name$="-' + suffix + '"]');
            
            if ($select.length > 0) {
                // (1) 요일 필터 UI 생성
                if ($select.prev('.day-filter-box').length === 0) {
                    const $dayFilter = $('<select class="day-filter-box" style="margin-right:8px; padding:4px; border:1px solid #ccc; border-radius:4px; background:#fff;">')
                        .append('<option value="">📅 요일 선택 (전체)</option>')
                        .append('<option value="월요일">월요일</option>')
                        .append('<option value="화요일">화요일</option>')
                        .append('<option value="수요일">수요일</option>')
                        .append('<option value="목요일">목요일</option>')
                        .append('<option value="금요일">금요일</option>')
                        .append('<option value="토요일">토요일</option>')
                        .append('<option value="일요일">일요일</option>');
                    
                    $select.before($dayFilter);

                    // (2) 요일 필터 이벤트 연결
                    $dayFilter.on('change', function() {
                        const selectedDay = $(this).val();
                        
                        // [중요] 해당 드롭다운 전용으로 필터링된 "원본 데이터"를 가져옴
                        const $originalOptions = $select.data('filtered-options');
                        
                        if (!$originalOptions) return;

                        $select.empty();

                        $originalOptions.each(function() {
                            const text = $(this).text();
                            const value = $(this).val();
                            
                            // 빈 값(-----)이거나, 선택한 요일이 포함된 경우만 표시
                            if (value === "" || selectedDay === "" || text.indexOf(selectedDay) !== -1) {
                                $select.append($(this).clone());
                            }
                        });
                        
                        // 필터링 후 첫 번째 값 선택 (UX 향상)
                        if ($select.children('option').length > 1 && !$select.val()) {
                            // $select.val($select.children('option').eq(1).val()); 
                        }
                    });
                }
                
                // 나중에 업데이트하기 위해 저장 (필터 키워드 포함)
                targetSelects.push({
                    '$element': $select,
                    'keyword': fieldFilters[suffix]
                });
            }
        });


        // 2. 지점 변경 시 실행될 함수
        function updateClassTimes() {
            var branchId = $branchSelect.val();

            if (!branchId) {
                // 지점 선택 안 함 -> 모두 초기화
                targetSelects.forEach(function(target) {
                    target.$element.html('<option value="">---------</option>');
                    target.$element.data('filtered-options', null);
                });
                return;
            }

            // 서버 요청
            $.ajax({
                url: '/core/api/get-classtimes/',
                data: { 'branch_id': branchId },
                success: function(data) {
                    // 전체 데이터(data)를 받아서, 각 드롭다운 입맛에 맞게 채반으로 거름(Filter)
                    
                    targetSelects.forEach(function(target) {
                        var $select = target.$element;
                        var filterKeyword = target.keyword;

                        var newOptionsHtml = '<option value="">---------</option>';
                        
                        // [핵심] 데이터 중에서 키워드가 포함된 것만 골라냄
                        $.each(data, function(index, item) {
                            // 키워드가 없거나(전체표시), 이름에 키워드가 포함된 경우만 추가
                            if (filterKeyword === "" || item.name.indexOf(filterKeyword) !== -1) {
                                newOptionsHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                            }
                        });

                        // 1. 드롭다운 내용 교체
                        var $newOptionsObj = $(newOptionsHtml);
                        var currentVal = $select.val(); // 기존 선택값 기억

                        $select.empty().append($newOptionsObj.clone());

                        // 2. [중요] 요일 필터용 "원본 데이터"로 저장 (이게 섞이면 안 됨!)
                        $select.data('filtered-options', $newOptionsObj.clone());

                        // 3. 요일 필터 초기화
                        $select.prev('.day-filter-box').val('');

                        // 4. 기존 값 복구 시도
                        if (currentVal) {
                            $select.val(currentVal);
                        }
                    });
                }
            });
        }

        // 3. 이벤트 연결
        if ($branchSelect.length) {
            $branchSelect.change(updateClassTimes);
            
            // 수정 화면일 경우: 현재 HTML에 있는 옵션들을 원본으로 저장해둬야 함
            if ($branchSelect.val()) {
                targetSelects.forEach(function(target) {
                    // 처음 로딩 시에는 필터링 로직 없이 현재 있는 그대로를 원본으로 잡음
                    target.$element.data('filtered-options', target.$element.find('option').clone());
                });
            }
        }
    });
})(django.jQuery);