import os
import json
import glob
import pandas as pd
from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    abort
)

# ───────────────────────────────────────────────────────────
# 앱 초기화: static_folder 를 “frontend” 로 지정
# ───────────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder="frontend",     # 실제 정적 자원(HTML/JS/CSS/이미지 등)이 들어있는 디렉터리
    static_url_path=""            # URL 경로를 /static 이 아닌 루트 경로(“”)에 연결
)

# ───────────────────────────────────────────────────────────
# 설정: CSV 파일 / 시험(회차) 디렉터리 위치
# ───────────────────────────────────────────────────────────

# 학생 목록(인증용) CSV 파일 경로
STUDENT_LIST_CSV = os.path.join(os.getcwd(), "student_list.csv")

# 전체 시험(회차)이 모여 있는 상위 디렉터리
EXAMS_DIR = os.path.join(os.getcwd(), "exams")


# ───────────────────────────────────────────────────────────
#  Utility 함수들
# ───────────────────────────────────────────────────────────

def load_valid_ids():
    """
    student_list.csv 파일의 첫 번째 열을 모두 읽어서
    “인증 가능한 리클래스 ID 목록”을 반환한다.
    """
    if not os.path.isfile(STUDENT_LIST_CSV):
        return []
    df = pd.read_csv(STUDENT_LIST_CSV, header=None, dtype=str)
    # 첫 번째 열만 인증 ID 로 간주
    return df.iloc[:, 0].astype(str).str.strip().tolist()


def list_all_exams():
    """
    exams 디렉터리 밑에 있는 모든 하위 폴더(회차) 이름을 반환
    """
    if not os.path.isdir(EXAMS_DIR):
        return []
    items = []
    for name in os.listdir(EXAMS_DIR):
        full = os.path.join(EXAMS_DIR, name)
        if os.path.isdir(full):
            items.append(name)
    return sorted(items)


def get_student_ids_for_exam(exam_name):
    """
    주어진 회차(exam_name) 디렉터리 안의 student_answer 폴더 밑을 전부 뒤져서
    “회원별 리클래스 ID” 목록을 만든다.
    student_answer/*.csv 파일들이 있고,
    각 CSV의 첫 열: 이름, 두 번째 열: 전화번호(‘010-xxxx-xxxx’), 나머지 열: 답안
    → 이름 + 전화번호 뒷 8자리(“010” 제외) 조합 ⇒ 리클래스ID 로 간주
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    sa_dir = os.path.join(exam_dir, "student_answer")
    if not os.path.isdir(sa_dir):
        return set()

    valid_ids = set()
    for csv_path in glob.glob(os.path.join(sa_dir, "*.csv")):
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except:
            continue
        for _, row in df.iterrows():
            name = str(row.iloc[0]).strip()
            phone = str(row.iloc[1]).strip().replace("-", "")
            phone_suffix = phone[-8:] if len(phone) >= 8 else phone
            sid = f"{name}{phone_suffix}"
            valid_ids.add(sid)
    return valid_ids


def find_reportcard_path(exam_name, student_id):
    """
    회차 디렉터리(exam_name) 안의 “report card” 폴더를 순회하며
    파일 이름이 “{student_id}_Spurt 모의고사 {회차번호}회_성적표.png” 와
    일치하는지 검사. 있으면 전체 경로를 반환하고, 없으면 None 반환.
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    rc_dir = os.path.join(exam_dir, "report card")
    if not os.path.isdir(rc_dir):
        return None

    # 예: student_id = "홍길동1234", exam_name = "Spurt 모의고사 07회"
    # 찾아야 할 파일명 예시: "홍길동1234_Spurt 모의고사 07회_성적표.png"
    target_filename = f"{student_id}_{exam_name}_성적표.png"
    for root, _, files in os.walk(rc_dir):
        for fn in files:
            if fn == target_filename:
                return os.path.join(root, fn)
    return None


def get_answer_key_for_exam(exam_name):
    """
    주어진 회차 디렉터리(exam_name) 안의 answer/*.csv 를 읽어서
    “문항 번호(1번부터 순서대로) → 정답 값” 맵을 리턴.
    CSV 구조(예시)
        header=None 으로 읽고,
        df.iloc[1:, 1:3] 에서 [문제번호, 정답]이 있다고 가정
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    ans_dir = os.path.join(exam_dir, "answer")
    if not os.path.isdir(ans_dir):
        return {}

    files = glob.glob(os.path.join(ans_dir, "*.csv"))
    if not files:
        return {}

    try:
        df = pd.read_csv(files[0], header=None, dtype=str)
    except:
        return {}

    ans_map = {}
    raw = df.iloc[1:, 1:3].reset_index(drop=True)
    for i, row in raw.iterrows():
        try:
            correct = int(str(row.iloc[0]).strip())
            ans_map[i + 1] = correct
        except:
            continue
    return ans_map


def get_student_answers_for_exam_and_id(exam_name, student_id):
    """
    회차(exam_name) 안의 student_answer/*.csv 에서
    “학생ID(이름+전화번호 뒷8자리)”가 일치하는 행(row)을 찾아,
    나머지 열(문항별 답안)들을 리스트로 리턴.
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    sa_dir = os.path.join(exam_dir, "student_answer")
    if not os.path.isdir(sa_dir):
        return []

    for csv_path in glob.glob(os.path.join(sa_dir, "*.csv")):
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except:
            continue
        for _, row in df.iterrows():
            name = str(row.iloc[0]).strip()
            phone = str(row.iloc[1]).strip().replace("-", "")
            phone_suffix = phone[-8:] if len(phone) >= 8 else phone
            sid = f"{name}{phone_suffix}"
            if sid == student_id:
                answers = []
                for i in range(2, len(row)):
                    val = str(row.iloc[i]).strip()
                    if not val or not val.isdigit():
                        answers.append("")  # 빈칸 혹은 숫자가 아닐 때 “틀린 문제” 처리
                    else:
                        answers.append(val)
                return answers
    return []


# ───────────────────────────────────────────────────────────
#  API 1) /api/authenticate
#    → student_list.csv 첫 번째 열(리클래스ID)이 있으면 authenticated=True
# ───────────────────────────────────────────────────────────
@app.route("/api/authenticate")
def api_authenticate():
    req_id = request.args.get("id", "").strip()
    if not req_id:
        return jsonify({"authenticated": False})

    valid_ids = load_valid_ids()
    return jsonify({"authenticated": (req_id in valid_ids)})


# ───────────────────────────────────────────────────────────
#  API 2) /api/exams
#    → 현재 exams 디렉터리 밑에 있는 “회차(폴더명)” 전체를 반환
# ───────────────────────────────────────────────────────────
@app.route("/api/exams")
def api_exams():
    exams = list_all_exams()
    return jsonify(exams)


# ───────────────────────────────────────────────────────────
#  API 3) /api/check_exam?exam=XXX&id=YYY
#    → 회차가 존재하고, 해당 회차의 student_answer 에 “YYY”가 있으면 registered=True
# ───────────────────────────────────────────────────────────
@app.route("/api/check_exam")
def api_check_exam():
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"registered": False, "error": "잘못된 요청입니다."})

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"registered": False, "error": "존재하지 않는 회차입니다."})

    student_ids = get_student_ids_for_exam(exam)
    if sid in student_ids:
        return jsonify({"registered": True})
    else:
        return jsonify({"registered": False, "error": "응시 정보가 없습니다."})


# ───────────────────────────────────────────────────────────
#  API 4) /api/reportcard?exam=XXX&id=YYY
#    → 특정 회차에서 특정 학생ID의 성적표를 리턴(이미지 URL)
# ───────────────────────────────────────────────────────────
@app.route("/api/reportcard")
def api_reportcard():
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"url": None, "error": "잘못된 요청입니다."})

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"url": None, "error": "존재하지 않는 회차입니다."})

    img_path = find_reportcard_path(exam, sid)
    if img_path and os.path.isfile(img_path):
        # 클라이언트(프론트엔드)에서 <img src="..."> 로 호출할 수 있도록 URL을 만들어준다.
        return jsonify({
            "url": f"/api/reportcard_image?exam={json.dumps(exam)}&id={json.dumps(sid)}"
        })
    else:
        return jsonify({"url": None, "error": "성적표를 찾을 수 없습니다."})


@app.route("/api/reportcard_image")
def api_reportcard_image():
    exam = request.args.get("exam", "").strip().strip('"')
    sid = request.args.get("id", "").strip().strip('"')
    if not exam or not sid:
        return abort(404)

    img_path = find_reportcard_path(exam, sid)
    if img_path and os.path.isfile(img_path):
        return send_file(img_path)
    else:
        return abort(404)


# ───────────────────────────────────────────────────────────
#  API 5) /api/wrong_questions?exam=XXX&id=YYY
#    → 틀린 문제 번호 목록(리스트) 반환
# ───────────────────────────────────────────────────────────
@app.route("/api/wrong_questions")
def api_wrong_questions():
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"wrongs": None, "error": "잘못된 요청입니다."})

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"wrongs": None, "error": "존재하지 않는 회차입니다."})

    student_ids = get_student_ids_for_exam(exam)
    if sid not in student_ids:
        return jsonify({"wrongs": None, "error": "응시 정보가 없습니다."})

    answer_key = get_answer_key_for_exam(exam)
    student_answers = get_student_answers_for_exam_and_id(exam, sid)
    if not student_answers:
        return jsonify({"wrongs": None, "error": "학생 답안을 찾을 수 없습니다."})

    wrongs = []
    for i, ans in enumerate(student_answers):
        qnum = i + 1
        correct = answer_key.get(qnum)
        if correct is None:
            continue
        if not ans or not ans.isdigit() or int(ans) != correct:
            wrongs.append(qnum)

    return jsonify({"wrongs": wrongs})


# ───────────────────────────────────────────────────────────
#  API 6) /api/submit_answer  (프론트엔드가 POST 로 찍어 주면
#    → { “correct”: True/False, “correctAnswer”: 정답 } 리턴)
# ───────────────────────────────────────────────────────────
@app.route("/api/submit_answer", methods=["POST"])
def api_submit_answer():
    data = request.get_json() or {}
    exam = data.get("exam", "").strip()
    sid = data.get("id", "").strip()
    qnum = data.get("question")
    ans = data.get("answer")

    if not exam or not sid or qnum is None or ans is None:
        return jsonify({"error": "잘못된 요청입니다."}), 400

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"error": "존재하지 않는 회차입니다."}), 400

    answer_key = get_answer_key_for_exam(exam)
    correct_ans = answer_key.get(int(qnum))
    if correct_ans is None:
        return jsonify({"error": "해당 문제를 찾을 수 없습니다."}), 404

    try:
        chosen = int(ans)
    except:
        chosen = None

    if chosen == correct_ans:
        return jsonify({"correct": True, "correctAnswer": correct_ans})
    else:
        return jsonify({"correct": False, "correctAnswer": correct_ans})


# ───────────────────────────────────────────────────────────
#  모든 그 외의 요청(GET /path)을 index.html 로 라우팅
# ───────────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    # 1) path가 빈 문자열이 아니고, 실제로 "frontend/" 폴더 안에 존재하는 파일이라면
    #    그대로 send_file 한다.
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_file(os.path.join(app.static_folder, path))

    # 2) 그렇지 않으면 "frontend/index.html" 파일을 보내준다.
    return send_file(os.path.join(app.static_folder, "index.html"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


