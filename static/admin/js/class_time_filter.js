/* static/admin/js/class_time_filter.js */

(function($) {
    $(document).ready(function() {
        console.log("🚀 시간표 필터(지점연동+요일검색) 스크립트 시작!");

        // 1. 제어할 요소들 찾기
        var $branchSelect = $('select[name$="-branch"]'); // 지점 선택 박스
        
        // 시간표 필드들의 접미사
        const targetSuffixes = ['syntax_class', 'reading_class', 'extra_class'];

        // 각 시간표 select 박스마다 "요일 필터" UI를 만들어 붙입니다.
        // 그리고 나중에 제어하기 위해 객체에 저장해둡니다.
        var targetSelects = [];

        targetSuffixes.forEach(function(suffix) {
            const $select = $('select[name$="-' + suffix + '"]');
            
            if ($select.length > 0) {
                // (1) 요일 필터 UI 생성 (기존 코드 활용)
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

                    // (2) 요일 필터 동작 연결
                    // 주의: 이제는 options가 서버에서 계속 바뀌므로, 이벤트 안에서 그때그때 options를 잡아야 함
                    $dayFilter.on('change', function() {
                        const selectedDay = $(this).val();
                        
                        // 현재 select 박스에 있는 모든 옵션을 기준으로 필터링
                        // (하지만 숨겨진 원본 데이터가 필요하므로 data 속성에 저장된 원본을 씁니다)
                        const $originalOptions = $select.data('all-options');
                        
                        if (!$originalOptions) return; // 아직 데이터가 없으면 패스

                        $select.empty(); // 일단 비우고

                        $originalOptions.each(function() {
                            const text = $(this).text();
                            const value = $(this).val();
                            
                            // 값이 비었거나(----), 선택한 요일이 텍스트에 포함되면 추가
                            if (value === "" || selectedDay === "" || text.indexOf(selectedDay) !== -1) {
                                $select.append($(this).clone());
                            }
                        });
                    });
                }
                
                targetSelects.push($select);
            }
        });


        // 2. 지점 변경 시 실행될 함수 (서버에서 시간표 가져오기)
        function updateClassTimes() {
            var branchId = $branchSelect.val();

            // 지점이 없으면 초기화
            if (!branchId) {
                $.each(targetSelects, function(idx, $select) {
                    $select.html('<option value="">---------</option>');
                    $select.data('all-options', null); // 저장된 원본 데이터 삭제
                });
                return;
            }

            // 서버에 요청 (AJAX)
            $.ajax({
                url: '/core/api/get-classtimes/',  // 아까 만든 URL
                data: { 'branch_id': branchId },
                success: function(data) {
                    console.log("✅ 서버에서 시간표 수신 완료:", data.length + "개");

                    // 받아온 데이터로 <option> 태그들 생성
                    var newOptionsHtml = '<option value="">---------</option>';
                    $.each(data, function(index, item) {
                        newOptionsHtml += '<option value="' + item.id + '">' + item.name + '</option>';
                    });
                    
                    // 메모리 상에 jQuery 객체로 만들어둠 (필터링 원본용)
                    var $newOptionsObj = $(newOptionsHtml);

                    // 3개의 시간표 select 박스를 모두 업데이트
                    $.each(targetSelects, function(idx, $select) {
                        // (1) 현재 선택된 값 기억 (있다면)
                        var currentVal = $select.val();

                        // (2) 화면 업데이트
                        $select.empty().append($newOptionsObj.clone());

                        // (3) [중요] 필터링을 위해 "원본 데이터"를 해당 태그에 심어둠 (.data 사용)
                        $select.data('all-options', $newOptionsObj.clone());

                        // (4) 요일 필터 초기화 (전체 보기로)
                        $select.prev('.day-filter-box').val('');

                        // (5) 기존에 선택했던 값이 새 목록에도 있으면 유지
                        // (없으면 1번째 옵션 선택됨)
                         if (currentVal) {
                             $select.val(currentVal);
                         }
                    });
                },
                error: function(xhr, status, error) {
                    console.error("시간표 가져오기 실패:", error);
                }
            });
        }

        // 3. 이벤트 리스너 연결
        if ($branchSelect.length) {
            $branchSelect.change(updateClassTimes);
            
            // (선택사항) 페이지 로딩 시 이미 지점이 선택되어 있으면(수정 화면) 실행
             if ($branchSelect.val()) {
                 // updateClassTimes(); // 필요하면 주석 해제 (단, 기존 선택값이 날아갈 수 있어 주의)
                 
                 // 수정 화면일 경우: 현재 HTML에 있는 옵션들을 '원본 데이터'로 저장해놔야 요일 필터가 작동함
                 $.each(targetSelects, function(idx, $select) {
                     $select.data('all-options', $select.find('option').clone());
                 });
             }
        }
    });
})(django.jQuery);