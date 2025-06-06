import os
import csv
from flask import Flask, request, jsonify, send_from_directory, abort

app = Flask(
    __name__,
    static_folder="frontend",        # 프론트엔드 정적 리소스(HTML, JS, CSS, 이미지 등)
    static_url_path=""               # 최상위 URL(“/”)로 접근 가능
)

# ─────────────────────────────────────────────────────────────────────────────
# 1) 상수 설정
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, "data")
STUDENT_LIST_CSV = os.path.join(DATA_DIR, "student_list.csv")

# ─────────────────────────────────────────────────────────────────────────────
# 2) 정적 파일 서빙 (HTML / CSS / JS / 아이콘 / GIF 등)
# ─────────────────────────────────────────────────────────────────────────────
# “/” 로 접속하면 index.html 반환
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

# frontend 내부의 다른 정적 파일(icons, globe.gif 등)은 Flask가 자동으로 처리합니다.
# (static_folder="frontend"로 지정했기 때문에, /icons/xxx, /globe.gif 등은 모두 frontend/icons/xxx, frontend/globe.gif 에서 불러옵니다.)

# 2-1) Exam 문제 이미지 서빙: /exam_images/{exam}/{파일명}
@app.route('/exam_images/<path:exam>/<path:filename>')
def serve_exam_image(exam, filename):
    """ data/{exam}/exam_images/{filename} """
    exam_folder = os.path.join(DATA_DIR, exam, "exam_images")
    if not os.path.isdir(exam_folder):
        return abort(404)
    return send_from_directory(exam_folder, filename)

# 2-2) ReportCard 이미지 서빙: /report/{exam}/{파일명}
@app.route('/report/<path:exam>/<path:filename>')
def serve_report_card(exam, filename):
    """ data/{exam}/report card/{filename} """
    report_folder = os.path.join(DATA_DIR, exam, "report card")
    if not os.path.isdir(report_folder):
        return abort(404)
    return send_from_directory(report_folder, filename)

# ─────────────────────────────────────────────────────────────────────────────
# 3) API: /api/authenticate
#     → student_list.csv 첫 열(리클래스 ID)만 비교
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/authenticate")
def api_authenticate():
    input_id = request.args.get("id", "").strip()
    if not input_id:
        return jsonify({"authenticated": False})

    authenticated = False
    try:
        with open(STUDENT_LIST_CSV, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 1:
                    continue
                stored_id = row[0].strip()
                if stored_id == input_id:
                    authenticated = True
                    break
    except Exception as e:
        print(f"[ERROR] /api/authenticate 예외: {e}")
        authenticated = False

    return jsonify({"authenticated": authenticated})

# ─────────────────────────────────────────────────────────────────────────────
# 4) API: /api/exams
#     → data/ 폴더 하위의 “서브디렉터리”를 목록으로 반환 (등록된 회차들)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/exams")
def api_exams():
    try:
        items = os.listdir(DATA_DIR)
        # 폴더만 필터링 (파일은 무시)
        exams = [d for d in items if os.path.isdir(os.path.join(DATA_DIR, d))]
        return jsonify(exams)
    except Exception as e:
        print(f"[ERROR] /api/exams 예외: {e}")
        return jsonify([])

# ─────────────────────────────────────────────────────────────────────────────
# 5) API: /api/check_exam
#     → data/{exam}/student_answer/ 폴더에서 “이름+전화번호 뒷8자리” 조합으로
#       로그인 ID와 비교하여 **응시 여부** 판정
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/check_exam")
def api_check_exam():
    exam = request.args.get("exam", "").strip()
    input_id = request.args.get("id", "").strip()
    if not exam or not input_id:
        return jsonify({"registered": False, "error": "파라미터가 잘못되었습니다."})

    # 해당 exam 폴더의 student_answer 폴더 경로
    student_answer_folder = os.path.join(DATA_DIR, exam, "student_answer")

    if not os.path.isdir(student_answer_folder):
        return jsonify({"registered": False, "error": "응시 정보가 없습니다."})

    found = False
    try:
        for fname in os.listdir(student_answer_folder):
            if not fname.lower().endswith(".csv"):
                continue
            csv_path = os.path.join(student_answer_folder, fname)
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2:
                        continue
                    name = row[0].strip()
                    phone_raw = row[1].strip()
                    # 전화번호에서 뒷 8자리만 추출
                    if "-" in phone_raw:
                        suffix = phone_raw.split("-")[-1]
                    else:
                        suffix = phone_raw[-8:]
                    student_id = f"{name}{suffix}"
                    if student_id == input_id:
                        found = True
                        break
                if found:
                    break
    except Exception as e:
        print(f"[ERROR] /api/check_exam 예외: {e}")
        return jsonify({"registered": False, "error": "응시 여부 확인 중 오류가 발생했습니다."})

    if found:
        return jsonify({"registered": True})
    else:
        return jsonify({"registered": False, "error": "해당 모의고사 응시 정보가 없습니다."})

# ─────────────────────────────────────────────────────────────────────────────
# 6) API: /api/reportcard
#     → data/{exam}/report card/ 폴더에서 해당 학생의 성적표 이미지 경로를 찾아 반환
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/reportcard")
def api_reportcard():
    exam = request.args.get("exam", "").strip()
    input_id = request.args.get("id", "").strip()
    if not exam or not input_id:
        return jsonify({"url": None, "error": "파라미터가 잘못되었습니다."})

    report_folder = os.path.join(DATA_DIR, exam, "report card")
    if not os.path.isdir(report_folder):
        return jsonify({"url": None, "error": "성적표가 없습니다."})

    # 보고자 하는 파일명: "{student_id}_{exam}_성적표.png" (또는 .PNG 등 대소문자 무관)
    found_file = None
    try:
        for fname in os.listdir(report_folder):
            # 대소문자 구분 없이 비교
            if fname.lower().startswith(input_id.lower()) and fname.lower().endswith(".png"):
                found_file = fname
                break
        if found_file:
            # 프론트엔드에서는 <img src="http://서버주소/report/{exam}/{found_file}" /> 로 불러옴
            url = f"/report/{exam}/{found_file}"
            return jsonify({"url": url})
        else:
            return jsonify({"url": None, "error": "성적표를 찾을 수 없습니다."})
    except Exception as e:
        print(f"[ERROR] /api/reportcard 예외: {e}")
        return jsonify({"url": None, "error": "성적표 로드 중 오류가 발생했습니다."})

# ─────────────────────────────────────────────────────────────────────────────
# 7) API: /api/wrong_questions
#     → data/{exam}/student_answer/에서 해당 학생의 답안 행을 찾아서, 
#       data/{exam}/answer/A.csv 와 비교 → 틀린 문제 번호 배열 반환
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/wrong_questions")
def api_wrong_questions():
    exam = request.args.get("exam", "").strip()
    input_id = request.args.get("id", "").strip()
    if not exam or not input_id:
        return jsonify({"wrong_questions": []})

    student_answer_folder = os.path.join(DATA_DIR, exam, "student_answer")
    answer_csv = os.path.join(DATA_DIR, exam, "answer", "A.csv")
    if not os.path.isdir(student_answer_folder) or not os.path.isfile(answer_csv):
        return jsonify({"wrong_questions": []})

    # 1) “이름+전화번호 뒷8자리” 로 student row 찾기
    student_row = None
    try:
        for fname in os.listdir(student_answer_folder):
            if not fname.lower().endswith(".csv"):
                continue
            csv_path = os.path.join(student_answer_folder, fname)
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2:
                        continue
                    name = row[0].strip()
                    phone_raw = row[1].strip()
                    if "-" in phone_raw:
                        suffix = phone_raw.split("-")[-1]
                    else:
                        suffix = phone_raw[-8:]
                    student_id = f"{name}{suffix}"
                    if student_id == input_id:
                        student_row = row[2:]  # 3열부터 실제 student의 선택/응답(1,2,3,…)이 들어있다고 가정
                        break
                if student_row is not None:
                    break
    except Exception as e:
        print(f"[ERROR] /api/wrong_questions - 학생 답안 탐색 중 예외: {e}")
        return jsonify({"wrong_questions": []})

    if not student_row:
        # 해당 학생의 답안을 못 찾음 → 틀린 문제 없음
        return jsonify({"wrong_questions": []})

    # 2) 정답 CSV(A.csv)에서 정답 열만 뽑아서 비교 (두 번째 행부터 문제별 정보가 있다고 가정)
    correct_answers = []
    try:
        with open(answer_csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
            # 보통 A.csv는 두 번째 행부터 “문제번호,정답,배점,문제유형” 식으로 되어 있으므로, [1:] 부터 사용
            for r in rows[1:]:
                # r[1] 에 정답(숫자) 형식이라고 가정
                try:
                    correct_answers.append(int(str(r[1]).strip()))
                except:
                    correct_answers.append(None)
    except Exception as e:
        print(f"[ERROR] /api/wrong_questions - 정답 CSV 로드 예외: {e}")
        return jsonify({"wrong_questions": []})

    # 3) student_row(3열부터…) 의 답안(예: “1”, “2”, 빈칸 등)과 correct_answers 비교
    wrong_list = []
    for idx, ans in enumerate(student_row):
        ans_str = str(ans).strip()
        # 빈칸(미응답)이거나, 숫자가 아니거나, 숫자이더라도 정답과 다르면 틀린 문제
        if not ans_str.isdigit():
            wrong_list.append(idx + 1)  # 문제번호 = idx+1
        else:
            try:
                if correct_answers[idx] is None or int(ans_str) != correct_answers[idx]:
                    wrong_list.append(idx + 1)
                # 정답일 경우 넘어감
            except:
                wrong_list.append(idx + 1)

    return jsonify({"wrong_questions": wrong_list})

# ─────────────────────────────────────────────────────────────────────────────
# 8) API: /api/review_question
#     → 특정 문제 번호에 대한 이미지 URL 반환
#       (별도의 보기 데이터는, 이미지 안에 포함되어 있다고 가정)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/review_question")
def api_review_question():
    exam = request.args.get("exam", "").strip()
    input_id = request.args.get("id", "").strip()
    try:
        qno = int(request.args.get("question", "").strip())
    except:
        return jsonify({"image_url": None})

    # 문제 이미지 경로: data/{exam}/exam_images/{qno}.png (또는 다른 확장자)
    # “정확히 어떤 확장자”인지는 미리 맞춰서 저장해야 합니다.
    # 여기서는 “.png”로 가정
    image_folder = os.path.join(DATA_DIR, exam, "exam_images")
    if not os.path.isdir(image_folder):
        return jsonify({"image_url": None})

    # 실제 파일명(예: "1.png", "2.png", …). 확장자가 다를 수 있으므로, 폴더 내에 qno로 시작하는 파일을 검색
    found_img = None
    try:
        for fname in os.listdir(image_folder):
            name_only, ext = os.path.splitext(fname)
            if name_only == str(qno):
                found_img = fname
                break
    except Exception as e:
        print(f"[ERROR] /api/review_question 예외: {e}")
        return jsonify({"image_url": None})

    if found_img:
        url = f"/exam_images/{exam}/{found_img}"
        return jsonify({
            "question": qno,
            "image_url": url,
            // 선지는 이미지 안에 들어 있다고 가정 → 별도 전달하지 않습니다.
            "choices": [1, 2, 3, 4, 5]
        })
    else:
        return jsonify({"image_url": None})

# ─────────────────────────────────────────────────────────────────────────────
# 9) API: /api/submit_review
#     → 사용자가 선택한 답(1~5)과 정답을 비교하여 True/False + 간단 해설 반환
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/submit_review")
def api_submit_review():
    exam = request.args.get("exam", "").strip()
    input_id = request.args.get("id", "").strip()
    try:
        qno = int(request.args.get("question", "").strip())
        selected = int(request.args.get("answer", "").strip())
    except:
        return jsonify({"correct": None})

    # 정답 CSV(A.csv)에서 해당 문제 번호의 정답을 가져옴
    answer_csv = os.path.join(DATA_DIR, exam, "answer", "A.csv")
    if not os.path.isfile(answer_csv):
        return jsonify({"correct": None})

    # CSV를 읽어서, 두 번째 행부터 qno 번째(인덱스 qno-1)의 정답 추출
    correct_answer = None
    try:
        with open(answer_csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
            # rows[1 + (qno-1)][1] 에 정답이 있다고 가정 (r[1] 컬럼)
            row_of_q = rows[1 + (qno - 1)]
            correct_answer = int(str(row_of_q[1]).strip())
    except Exception as e:
        print(f"[ERROR] /api/submit_review - 정답 추출 중 예외: {e}")
        return jsonify({"correct": None})

    correct_flag = (selected == correct_answer)
    # “해설”이 없다면 빈 문자열 리턴
    return jsonify({
        "correct": correct_flag,
        "correct_answer": correct_answer,
        "explanation": ""   # 필요 시 확장
    })

# ─────────────────────────────────────────────────────────────────────────────
# 10) API: /api/quiz  (OX 퀴즈 뼈대 – 추후 구현)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/quiz")
def api_quiz():
    # TODO: OX 퀴즈 기능 구현
    return jsonify({"quiz": []})

# ─────────────────────────────────────────────────────────────────────────────
# 11) 에러 핸들러
# ─────────────────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return "", 404

# ─────────────────────────────────────────────────────────────────────────────
# 12) 애플리케이션 실행
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 개발 환경에서 테스트용으로 5000 포트 사용
    app.run(host="0.0.0.0", port=5000, debug=True)

