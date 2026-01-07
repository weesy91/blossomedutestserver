(function($) {
    $(document).ready(function() {
        // ============================================================
        // [설정] 1. 분원 선택 박스와 시간표 박스들을 정의합니다.
        // ============================================================
        var $branchSelect = $('select[name$="-branch"]'); // 지점 선택 박스

        // 각 드롭다운별로 "어떤 글자"가 포함된 수업만 보여줄지 규칙을 정합니다.
        // key: 필드명 뒷부분, value: 필터링할 단어 (빈카시면 전체 표시)
        const fieldRules = [
            { field: 'syntax_class', keyword: '구문' },  // 구문 칸엔 '구문'만
            { field: 'reading_class', keyword: '독해' }, // 독해 칸엔 '독해'만
            { field: 'extra_class', keyword: '' }      // 추가 수업은 일단 다 보여줌
        ];

        // ============================================================
        // [기능 1] 요일 필터 박스 만들기 (UI 생성)
        // ============================================================
        function createDayFilter($targetSelect) {
            // 이미 필터가 있으면 만들지 않음
            if ($targetSelect.prev('.day-filter-box').length > 0) return;

            // 요일 선택 박스 HTML 생성
            const $dayFilter = $('<select class="day-filter-box" style="margin-right:8px; padding:4px; border:1px solid #ccc; border-radius:4px; background:#fff;">')
                .append('<option value="">📅 요일 선택 (전체)</option>')
                .append('<option value="월요일">월요일</option>')
                .append('<option value="화요일">화요일</option>')
                .append('<option value="수요일">수요일</option>')
                .append('<option value="목요일">목요일</option>')
                .append('<option value="금요일">금요일</option>')
                .append('<option value="토요일">토요일</option>')
                .append('<option value="일요일">일요일</option>');

            // 타겟 드롭다운 앞에 붙이기
            $targetSelect.before($dayFilter);

            // [이벤트] 요일 변경 시 동작
            $dayFilter.on('change', function() {
                const selectedDay = $(this).val();
                
                // [중요] "이 과목용으로 분류된 전체 목록"을 가져옵니다.
                const $masterList = $targetSelect.data('master-options'); 
                
                if (!$masterList) return; // 데이터가 없으면 중단

                // 기존 목록 비우기
                $targetSelect.empty();

                // 마스터 리스트에서 하나씩 꺼내서 검사
                $masterList.each(function() {
                    const text = $(this).text();  // 예: "월 19:00 (구문)"
                    const value = $(this).val();
                    
                    // (1) 빈 칸(------) 이거나
                    // (2) 전체 보기 모드 이거나
                    // (3) 텍스트에 "선택한 요일"이 들어있으면 -> 표시
                    if (value === "" || selectedDay === "" || text.indexOf(selectedDay) !== -1) {
                        $targetSelect.append($(this).clone());
                    }
                });
            });
        }

        // ============================================================
        // [기능 2] 서버에서 시간표 가져와서 -> 과목별로 나누기
        // ============================================================
        function updateClassTimes() {
            var branchId = $branchSelect.val();

            // 1. 지점이 선택 안 됐으면 -> 모두 초기화
            if (!branchId) {
                fieldRules.forEach(function(rule) {
                    const $select = $('select[name$="-' + rule.field + '"]');
                    $select.html('<option value="">---------</option>');
                    $select.data('master-options', null);
                });
                return;
            }

            // 2. 서버에 요청 (이 지점 시간표 다 줘!)
            $.ajax({
                url: '/core/api/get-classtimes/',
                data: { 'branch_id': branchId },
                success: function(data) {
                    // data = [{id:1, name:"월 19:00 (구문)"}, {id:2, name:"화 18:00 (독해)"} ...]

                    // 3. 받아온 데이터를 규칙에 맞춰 각 드롭다운에 분배
                    fieldRules.forEach(function(rule) {
                        const $select = $('select[name$="-' + rule.field + '"]');
                        if ($select.length === 0) return;

                        // (A) 분류하기 (Keyword Filtering)
                        var filteredHtml = '<option value="">---------</option>';
                        
                        $.each(data, function(index, item) {
                            // 규칙에 맞는 단어가 포함되어 있으면 추가
                            if (rule.keyword === "" || item.name.indexOf(rule.keyword) !== -1) {
                                filteredHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                            }
                        });

                        // (B) 드롭다운 업데이트
                        const $newOptions = $(filteredHtml);
                        const currentVal = $select.val(); // 기존 선택값 기억

                        $select.empty().append($newOptions);

                        // (C) [핵심] 요일 필터링을 위해 "이 과목의 전체 목록"을 저장해둠
                        $select.data('master-options', $newOptions.clone());

                        // (D) 요일 필터 초기화
                        $select.prev('.day-filter-box').val('');

                        // (E) 기존값 복구 시도
                        if (currentVal) {
                            $select.val(currentVal);
                        }
                    });
                }
            });
        }


        // ============================================================
        // [초기화] 페이지 로딩 시 실행
        // ============================================================
        
        // 1. 각 칸마다 요일 필터 박스 생성하기
        fieldRules.forEach(function(rule) {
            const $select = $('select[name$="-' + rule.field + '"]');
            if ($select.length > 0) {
                createDayFilter($select);
            }
        });

        // 2. 지점 변경 이벤트 연결
        if ($branchSelect.length) {
            $branchSelect.change(updateClassTimes);
            
            // 3. (수정 모드일 때) 이미 지점이 선택되어 있다면
            // 현재 화면에 있는 옵션들을 '마스터 데이터'로 저장해둬야 요일 필터가 먹힘
            if ($branchSelect.val()) {
                 fieldRules.forEach(function(rule) {
                    const $select = $('select[name$="-' + rule.field + '"]');
                    if ($select.length > 0) {
                        // 현재 있는 <option>들을 복사해서 저장
                        $select.data('master-options', $select.find('option').clone());
                    }
                });
            }
        }
    });
})(django.jQuery);