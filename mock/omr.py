import cv2
import numpy as np
import imutils
import traceback

def scan_omr(image_bytes, debug_mode=False):
    """
    [Core] OMR Engine v45 (Noise Rejection & ROI Fix)
    - 문제: 하단 영역 과다 확장으로 '감독관 확인란'을 9번 마킹으로 오인 -> 그리드 전체 밀림
    - 해결 1 (Size Filter): w, h가 55px을 넘는 큰 박스(감독관란 등)는 무조건 배제
    - 해결 2 (ROI 조정): 우측을 0.33까지 넓혀 8열 확보, 하단은 0.845로 제한
    - 결과: 순수하게 0~9번 동그라미만 추출하여 'Smart Anchor'가 정확하게 0번과 9번을 잡음
    """
    try:
        # 1. 이미지 로드
        if hasattr(image_bytes, 'read'):
            file_bytes = np.frombuffer(image_bytes.read(), np.uint8)
        else:
            file_bytes = np.frombuffer(image_bytes, np.uint8)
            
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None: return None, None

        target_height = 1600
        image = imutils.resize(image, height=target_height) 
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        (h, w) = gray.shape 
        debug_img = image.copy()

        # ---------------------------------------------------------
        # [Part A] 수험번호 판독 (노이즈 제거 강화)
        # ---------------------------------------------------------
        cnts = cv2.findContours(thresh.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        
        id_cnts = []
        
        # [수정 1] 탐색 영역 재조정
        # Right: 0.33 (마지막 2자리 포함)
        # Bottom: 0.845 (감독관란 배제)
        SEARCH_X_MIN, SEARCH_X_MAX = w * 0.08, w * 0.33 
        SEARCH_Y_MIN, SEARCH_Y_MAX = h * 0.44, h * 0.845

        all_bubbles_y = [] 

        for c in cnts:
            (x, y, w_box, h_box) = cv2.boundingRect(c)
            ar = w_box / float(h_box)
            cx, cy = x + w_box//2, y + h_box//2

            # [수정 2] 강력한 크기 필터링 (감독관 박스 제거)
            # 동그라미는 보통 20~45px 사이임. 55px 넘어가면 박스로 간주하고 무시.
            if 15 <= w_box <= 55 and 15 <= h_box <= 55:
                if 0.5 <= ar <= 2.0: # 비율도 좀 더 동그라미스럽게 제한
                    if SEARCH_X_MIN < cx < SEARCH_X_MAX and SEARCH_Y_MIN < cy < SEARCH_Y_MAX:
                        id_cnts.append((x, y, w_box, h_box, c))
                        all_bubbles_y.append(cy)

        # 2. [스마트 앵커] 0번과 9번 위치 찾기
        if len(all_bubbles_y) > 10:
            all_bubbles_y.sort()
            # 노이즈가 제거되었으므로, 가장 위가 0번, 가장 아래가 9번임이 확실함
            # 안정성을 위해 상위/하위 5개의 평균 사용
            top_k = min(5, len(all_bubbles_y) // 2)
            
            grid_top = np.mean(all_bubbles_y[:top_k])   # 0번 중심
            grid_bot = np.mean(all_bubbles_y[-top_k:])  # 9번 중심
        else:
            # 발견 실패 시 Fallback (이미지 비율 기반)
            grid_top = h * 0.465
            grid_bot = h * 0.803

        # 그리드 간격 계산
        grid_span = grid_bot - grid_top
        if grid_span <= 0: grid_span = 1
        row_step = grid_span / 9.0

        # 시각화
        if debug_mode:
            # 탐색 영역 (파란 점선)
            cv2.rectangle(debug_img, (int(SEARCH_X_MIN), int(SEARCH_Y_MIN)), 
                          (int(SEARCH_X_MAX), int(SEARCH_Y_MAX)), (255, 0, 0), 1)
            
            # 빨간 그리드 선 (0~9 중앙)
            for i in range(10):
                y_center = int(grid_top + (row_step * i))
                cv2.line(debug_img, (int(SEARCH_X_MIN), y_center), (int(SEARCH_X_MAX), y_center), (0, 0, 255), 2)

        student_id = ""
        if id_cnts:
            # X축 정렬 (컬럼 분리)
            id_cnts.sort(key=lambda k: k[0])
            id_cols = []
            curr_col = []
            prev_x = -100
            
            for c in id_cnts:
                if prev_x < 0 or abs(c[0] - prev_x) > 20:
                    if curr_col: id_cols.append(curr_col)
                    curr_col = [c]
                    prev_x = c[0]
                else: curr_col.append(c)
            if curr_col: id_cols.append(curr_col)

            # 열 개수 제한 (8자리만)
            valid_cols = id_cols[:8] 
            
            final_id_parts = []
            for col in valid_cols:
                max_px, best_y, best_rect = 0, -1, None
                
                # 후보군 박스 (하늘색)
                if debug_mode:
                    for (x, y, wb, hb, c) in col:
                        cv2.rectangle(debug_img, (x, y), (x+wb, y+hb), (255, 200, 0), 1)

                for (x, y, wb, hb, c) in col:
                    mask = np.zeros(thresh.shape, dtype="uint8")
                    cv2.drawContours(mask, [c], -1, 255, -1)
                    total = cv2.countNonZero(cv2.bitwise_and(thresh, thresh, mask=mask))
                    
                    if total > 50: 
                        if total > max_px: max_px, best_y, best_rect = total, y, (x, y, wb, hb)

                if best_y != -1:
                    mk_center_y = best_rect[1] + best_rect[3] // 2
                    
                    # 위치 매핑
                    raw_idx = (mk_center_y - grid_top) / row_step
                    idx = int(round(raw_idx))
                    
                    final_id_parts.append(str(max(0, min(9, idx))))
                    
                    # 최종 선택 (진한 파란색)
                    if debug_mode:
                        bx, by, bw, bh = best_rect
                        cv2.rectangle(debug_img, (bx, by), (bx+bw, by+bh), (255, 0, 0), 3)
                else:
                    final_id_parts.append("?")
            
            student_id = "".join(final_id_parts)

        # ---------------------------------------------------------
        # [Part B] 정답 판독 (기존 유지)
        # ---------------------------------------------------------
        bottom_h = int(h * 0.06) 
        bottom_roi = thresh[h - bottom_h : h, 0 : w]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 5))
        closed_bottom = cv2.morphologyEx(bottom_roi, cv2.MORPH_CLOSE, kernel)
        
        anchor_cnts = imutils.grab_contours(cv2.findContours(closed_bottom.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE))
        valid_anchors = []
        for c in anchor_cnts:
            (ax, ay, aw, ah) = cv2.boundingRect(c)
            global_y = (h - bottom_h) + ay
            if global_y >= h * 0.94 and aw > 40 and ah > 10:
                valid_anchors.append((ax + aw//2, global_y, aw, ah))
                if debug_mode: cv2.rectangle(debug_img, (ax, global_y), (ax+aw, global_y+ah), (0, 0, 255), 3)

        valid_anchors.sort(key=lambda x: x[0])
        filtered_anchors = [anc for anc in valid_anchors if anc[0] > w * 0.28]
        target_centers = [anc[0] for anc in filtered_anchors[-3:]] if len(filtered_anchors) >= 3 else [int(w * 0.35), int(w * 0.58), int(w * 0.81)]

        answers = []
        for center_x in target_centers:
            roi_x1, roi_x2 = max(0, center_x - 115), min(w, center_x + 115)
            roi_y_top, roi_y_bot = int(h * 0.135), int(h * 0.94) 
            col_roi_gray = gray[roi_y_top:roi_y_bot, roi_x1:roi_x2]
            col_thresh = cv2.threshold(col_roi_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            col_dilated = cv2.dilate(col_thresh, np.ones((4, 4), np.uint8), iterations=2)
            
            q_cnts = imutils.grab_contours(cv2.findContours(col_dilated.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE))
            bubbles = []
            for c in q_cnts:
                (bx, by, bw, bh) = cv2.boundingRect(c)
                if 8 <= bw <= 95 and 8 <= bh <= 95 and 0.4 <= bw/bh <= 2.5:
                    bubbles.append((bx, by, bw, bh, c))
                    if debug_mode: cv2.rectangle(debug_img, (roi_x1 + bx, roi_y_top + by), (roi_x1 + bx + bw, roi_y_top + by + bh), (255, 255, 0), 1)
            
            if not bubbles: continue
            bubbles.sort(key=lambda b: b[1])
            rows, curr_row, prev_y = [], [], -100
            for b in bubbles:
                if prev_y < 0 or abs(b[1] - prev_y) > 30:
                    if curr_row: curr_row.sort(key=lambda r: r[0]); rows.append(curr_row)
                    curr_row, prev_y = [b], b[1]
                else: curr_row.append(b)
            if curr_row: curr_row.sort(key=lambda r: r[0]); rows.append(curr_row)
            
            for row in rows:
                if len(row) < 5: continue
                row = row[-5:]
                if debug_mode:
                    row_center_y = row[0][1] + row[0][3] // 2
                    cv2.line(debug_img, (roi_x1, roi_y_top + row_center_y), (roi_x2, roi_y_top + row_center_y), (0, 165, 255), 1)
                
                bubbled_idx, max_px = None, 0
                for i, (bx, by, bw, bh, c) in enumerate(row):
                    mask = np.zeros(col_thresh.shape, dtype="uint8")
                    cv2.drawContours(mask, [c], -1, 255, -1) 
                    total = cv2.countNonZero(cv2.bitwise_and(col_thresh, col_thresh, mask=mask))
                    if total > 50:
                        if total > max_px: max_px, bubbled_idx = total, i + 1
                if bubbled_idx:
                    answers.append(bubbled_idx)
                    if debug_mode:
                        gx, gy, bw, bh = roi_x1 + row[bubbled_idx-1][0], roi_y_top + row[bubbled_idx-1][1], row[bubbled_idx-1][2], row[bubbled_idx-1][3]
                        cv2.rectangle(debug_img, (gx, gy), (gx+bw, gy+bh), (0, 255, 0), 2)

        if debug_mode:
            print(f"DEBUG: Student ID: {student_id}")
            cv2.imwrite("debug_result_final.jpg", debug_img)
        return student_id, answers
    except Exception:
        traceback.print_exc()
        return None, None

def calculate_score(student_answers, exam_info):
    """
    [Logic] 채점 및 통계 계산 함수 (views.py에서 중복 제거됨)
    """
    questions = exam_info.questions.all().order_by('number')
    total_score = 0
    wrong_counts = {'LISTENING': 0, 'VOCAB': 0, 'GRAMMAR': 0, 'READING': 0}
    wrong_question_numbers = [] 
    student_answers_dict = {}

    max_len = min(len(student_answers), len(questions))

    for i in range(max_len):
        student_ans = student_answers[i]
        question_obj = questions[i]
        student_answers_dict[str(question_obj.number)] = student_ans
        
        if student_ans == question_obj.correct_answer:
            total_score += question_obj.score
        else:
            cat = question_obj.category
            if cat == 'LISTENING': wrong_counts['LISTENING'] += 1
            elif cat in ['VOCAB', 'MEANING']: wrong_counts['VOCAB'] += 1
            elif cat == 'GRAMMAR': wrong_counts['GRAMMAR'] += 1
            else: wrong_counts['READING'] += 1
            wrong_question_numbers.append(question_obj.number)
    
    grade = 9
    if total_score >= 90: grade = 1
    elif total_score >= 80: grade = 2
    elif total_score >= 70: grade = 3
    elif total_score >= 60: grade = 4
    elif total_score >= 50: grade = 5
    elif total_score >= 40: grade = 6
    elif total_score >= 30: grade = 7
    elif total_score >= 20: grade = 8

    return {
        'score': total_score,
        'grade': grade,
        'wrong_counts': wrong_counts,
        'wrong_question_numbers': wrong_question_numbers,
        'student_answers_dict': student_answers_dict
    }