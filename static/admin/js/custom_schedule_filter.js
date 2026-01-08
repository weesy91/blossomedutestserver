/* static/admin/js/custom_schedule_filter.js */

(function($) {
    $(document).ready(function() {
        console.log("🚀 스케줄 필터(중복방지) 스크립트 시작됨!");

        // URL에서 현재 수정 중인 학생의 User ID 추출
        const urlMatch = window.location.pathname.match(/studentuser\/(\d+)\/change/);
        const currentStudentId = urlMatch ? urlMatch[1] : null;

        const mappings = [
            { role: 'syntax',  teacherSuffix: '-syntax_teacher',  classSuffix: '-syntax_class' },
            { role: 'reading', teacherSuffix: '-reading_teacher', classSuffix: '-reading_class' },
            { role: 'extra',   teacherSuffix: '-extra_class_teacher', classSuffix: '-extra_class' }
        ];

        // API를 통해 마감된 시간표를 비활성화하는 핵심 함수
        function checkAndDisable(teacherSelect, classSelect, role) {
            const teacherId = $(teacherSelect).val();
            const $timeSelect = $(classSelect);

            if (!teacherId) {
                // 선생님 선택 해제 시 -> 모두 활성화 및 텍스트 복구
                $timeSelect.find('option').prop('disabled', false).css('color', '').each(function() {
                    $(this).text($(this).text().replace(' ⛔(마감)', ''));
                });
                return;
            }

            const currentVal = $timeSelect.val(); 

            $.ajax({
                url: '/academy/api/admin/teacher-schedule/',
                data: {
                    'teacher_id': teacherId,
                    'subject': role,
                    'current_student_id': currentStudentId
                },
                success: function(response) {
                    const occupiedIds = response.occupied_ids;
                    // console.log(`[${role}] 마감 확인 완료. 비활성화 대상:`, occupiedIds);

                    $timeSelect.find('option').each(function() {
                        const optVal = parseInt($(this).val());
                        if (isNaN(optVal)) return; // 빈 옵션 제외

                        const isOccupied = occupiedIds.includes(optVal);
                        const isSelected = (optVal == currentVal);

                        let text = $(this).text().replace(' ⛔(마감)', '');

                        if (isOccupied && !isSelected) {
                            $(this).prop('disabled', true);
                            $(this).css('color', '#cccccc');
                            $(this).css('font-style', 'italic');
                            $(this).text(text + ' ⛔(마감)');
                        } else {
                            $(this).prop('disabled', false);
                            $(this).css('color', '');
                            $(this).css('font-style', '');
                            $(this).text(text);
                        }
                    });
                },
                error: function(err) {
                    console.error("중복 확인 API 에러:", err);
                }
            });
        }

        mappings.forEach(function(map) {
            // 1. 선생님 선택 박스 찾기
            const $teacherSelects = $(`select[id$="${map.teacherSuffix}"]`);
            
            $teacherSelects.each(function() {
                const $teacherSelect = $(this);
                const teacherId = $teacherSelect.attr('id');
                // 2. 짝꿍인 시간표 선택 박스 찾기
                const classId = teacherId.replace(map.teacherSuffix, map.classSuffix);
                const $classSelect = $(document.getElementById(classId));

                if ($classSelect.length > 0) {
                    // (A) 선생님을 바꿀 때 실행
                    $teacherSelect.on('change', function() {
                        checkAndDisable(this, $classSelect, map.role);
                    });

                    // (B) [핵심 추가] 시간표 목록이 갱신되었을 때도 실행 (class_time_filter.js 와의 연동)
                    $classSelect.on('options_refreshed', function() {
                        // console.log("♻️ 시간표 갱신 감지! 중복 검사 재실행");
                        checkAndDisable($teacherSelect[0], $classSelect, map.role);
                    });

                    // (C) 페이지 로딩 시 최초 실행
                    checkAndDisable(this, $classSelect, map.role);
                }
            });
        });
    });
})(django.jQuery);