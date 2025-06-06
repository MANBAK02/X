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

app = Flask(
    __name__,
    static_folder="static",       # 정적 파일(이미지, CSS, JS 등)은 /static 밑에서 제공
    static_url_path="/static"
)

# ===============================================
# 설정 (적절하게 경로를 프로젝트 상황에 맞게 수정하세요)
# ===============================================

# “student_list.csv” 파일 경로 (프로젝트 루트에 있다고 가정)
STUDENT_LIST_CSV = os.path.join(os.getcwd(), "student_list.csv")

# 모든 시험(회차) 폴더가 들어 있는 상위 디렉터리
EXAMS_DIR = os.path.join(os.getcwd(), "exams")
# └─ exams/
#      └─ Spurt 모의고사 05회/
#          ├─ answer/A.csv
#          ├─ student_answer/class1.csv, class2.csv, …
#          └─ report card/class1/…png, class2/…png


# ===============================================
#  Utility 함수들
# ===============================================

def load_valid_ids():
    """
    student_list.csv 를 읽어서, 로그인 가능한 리클래스ID 목록을 반환.
    첫 번째 열이 “리클래스ID”라고 가정.
    """
    if not os.path.isfile(STUDENT_LIST_CSV):
        return []
    df = pd.read_csv(STUDENT_LIST_CSV, header=None, dtype=str)
    valid_ids = df.iloc[:, 0].astype(str).str.strip().tolist()
    return valid_ids


def list_all_exams():
    """
    EXAMS_DIR 밑에서, “시험 이름” 폴더(디렉터리) 목록을 반환.
    └─ exams/Spurt 모의고사 05회/, Spurt 모의고사 06회/, …
    """
    if not os.path.isdir(EXAMS_DIR):
        return []
    items = []
    for name in os.listdir(EXAMS_DIR):
        full = os.path.join(EXAMS_DIR, name)
        if os.path.isdir(full):
            items.append(name)
    # 이름순 정렬
    return sorted(items)


def get_student_ids_for_exam(exam_name):
    """
    주어진 exam_name(예: “Spurt 모의고사 05회”)에서 응시자 목록(리클래스ID 리스트)을 반환.
    student_answer/*.csv 안의 각 반별 CSV를 읽어서, 
    첫열(이름) + 둘째열(전화번호 뒷8자리) 조합으로 “리클래스ID”를 만든다고 가정.
    리턴 값: ['강민엽1553', '곽명현4739', …]
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    sa_dir = os.path.join(exam_dir, "student_answer")
    valid_ids = []

    if not os.path.isdir(sa_dir):
        return []  # student_answer 폴더 자체가 없으면 빈 리스트

    # 모든 CSV 파일 읽기
    for csv_path in glob.glob(os.path.join(sa_dir, "*.csv")):
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except:
            continue
        # 첫열 = 이름, 둘째열 = 전화번호("010-" 제외한 뒷8자리 또는 "12345678" 형태)
        # 예: 이름="강민엽", 전화번호="1553" → student_id="강민엽1553"
        for _, row in df.iterrows():
            name = str(row.iloc[0]).strip()
            phone = str(row.iloc[1]).strip()
            # 혹시 전화번호에 하이픈(-)이 들어 있으면 뒤 8자리만 쓰도록
            phone_suffix = phone.replace("-", "")[-8:]
            sid = f"{name}{phone_suffix}"
            valid_ids.append(sid)
    return set(valid_ids)


def find_reportcard_path(exam_name, student_id):
    """
    report card 폴더 구조 안에서 {student_id}_Spurt 모의고사 {회차}회_성적표.png 파일을 찾는다.
    발견되면 절대경로를 반환, 못 찾으면 None 반환.
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    rc_dir = os.path.join(exam_dir, "report card")
    if not os.path.isdir(rc_dir):
        return None

    # 하위 모든 디렉터리를 순회하며 파일 이름 매칭
    target_filename = f"{student_id}_Spurt 모의고사 {exam_name.split()[-1]}_성적표.png"
    # exam_name.split()[-1] ⇒ “05회” 부분만 뽑아서 파일명에 맞추게 처리
    for root, _, files in os.walk(rc_dir):
        for fn in files:
            if fn == target_filename:
                return os.path.join(root, fn)
    return None


def get_answer_key_for_exam(exam_name):
    """
    answer 폴더 내의 CSV(A.csv)를 읽어서, 
    문제번호 → 정답(int) 매핑 dict 반환.
    """
    exam_dir = os.path.join(EXAMS_DIR, exam_name)
    ans_dir = os.path.join(exam_dir, "answer")
    if not os.path.isdir(ans_dir):
        return {}

    # answer/*.csv (하나만 있다고 가정)
    files = glob.glob(os.path.join(ans_dir, "*.csv"))
    if not files:
        return {}

    try:
        df = pd.read_csv(files[0], header=None, dtype=str)
    except:
        return {}

    # 두 번째 행(인덱스1) 이상에 실제 문제 정보가 있다고 가정
    # 여기서는 "문제번호, 정답, 배점, 문제유형" 순서라고 가정
    # 예제에서는 df.iloc[1:,1:5] 과 비슷하게 사용
    ans_map = {}
    raw = df.iloc[1:, 1:3]  # 컬럼1=정답, 컬럼2=배점(우리는 정답만 필요)
    raw = raw.reset_index(drop=True)
    # 문제번호는 그냥 1부터 순차적으로 붙여서 매핑
    for i, row in raw.iterrows():
        try:
            correct = int(row.iloc[0])
            ans_map[i + 1] = correct
        except:
            continue
    return ans_map


def get_student_answers_for_exam_and_id(exam_name, student_id):
    """
    주어진 exam_name의 student_answer/*.csv 안에서 “student_id”에 해당하는 학생의 답안 리스트(1~문제수) 반환.
    학생 답안은 DataFrame의 나머지 칼럼(3번째 칼럼 이후)에 순서대로 있다고 가정.
    반환: [answer1, answer2, …], 비어있으면 "" 문자열. 
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
        # “이름+전화번호” 조합으로 student_id와 일치하는 행 찾기
        for _, row in df.iterrows():
            name = str(row.iloc[0]).strip()
            phone = str(row.iloc[1]).strip().replace("-", "")[-8:]
            sid = f"{name}{phone}"
            if sid == student_id:
                # 답안 열은 그 이후 칼럼들(3번째 칼럼부터 끝까지)
                answers = []
                for i in range(2, len(row)):
                    val = str(row.iloc[i]).strip()
                    # 비어있거나 숫자가 아니면 빈답("")
                    if not val or not val.isdigit():
                        answers.append("")
                    else:
                        answers.append(val)
                return answers
    # 해당 학생 ID를 못 찾았으면 빈 리스트 반환
    return []


# ===============================================
#  API Endpoints
# ===============================================

@app.route("/api/authenticate")
def api_authenticate():
    """
    Query param: ?id={리클래스ID}
    student_list.csv 에서 확인 후 {authenticated:true/false} 반환
    """
    req_id = request.args.get("id", "").strip()
    if not req_id:
        return jsonify({"authenticated": False})

    valid_ids = load_valid_ids()
    if req_id in valid_ids:
        return jsonify({"authenticated": True})
    else:
        return jsonify({"authenticated": False})


@app.route("/api/exams")
def api_exams():
    """
    GET → 등록된 모든 시험(회차) 이름 리스트 반환
    """
    exams = list_all_exams()
    return jsonify(exams)


@app.route("/api/check_exam")
def api_check_exam():
    """
    Query param: ?exam={exam_name}&id={student_id}
    해당 학생이 해당 시험에 응시했는지 확인 → {registered: true/false, error(?): 메시지}
    """
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


@app.route("/api/reportcard")
def api_reportcard():
    """
    Query param: ?exam={exam_name}&id={student_id}
    해당 학생의 성적표 이미지 URL을 {url: "..."} 로 반환.
    """
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"url": None, "error": "잘못된 요청입니다."})

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"url": None, "error": "존재하지 않는 회차입니다."})

    img_path = find_reportcard_path(exam, sid)
    if img_path and os.path.isfile(img_path):
        # 직접 파일을 전송하는 엔드포인트를 호출할 수 있도록 URL 반환
        return jsonify({
            "url": f"/api/reportcard_image?exam={json.dumps(exam)}&id={json.dumps(sid)}"
        })
    else:
        return jsonify({"url": None, "error": "성적표를 찾을 수 없습니다."})


@app.route("/api/reportcard_image")
def api_reportcard_image():
    """
    실제 성적표 이미지를 send_file 로 반환
    Query param: ?exam="{exam_name}"&id="{student_id}"
    """
    exam = request.args.get("exam", "").strip().strip('"')
    sid = request.args.get("id", "").strip().strip('"')
    if not exam or not sid:
        return abort(404)

    img_path = find_reportcard_path(exam, sid)
    if img_path and os.path.isfile(img_path):
        return send_file(img_path)
    else:
        return abort(404)


@app.route("/api/wrong_questions")
def api_wrong_questions():
    """
    Query param: ?exam={exam_name}&id={student_id}
    해당 학생의 답안과 답안지(answer) 비교하여 틀린 문제 목록 반환 → {wrongs: [번호1, 번호2, …]}
    """
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"wrongs": None, "error": "잘못된 요청입니다."})

    valid_exams = list_all_exams()
    if exam not in valid_exams:
        return jsonify({"wrongs": None, "error": "존재하지 않는 회차입니다."})

    # 학생이 해당 시험에 응시했는지 확인
    student_ids = get_student_ids_for_exam(exam)
    if sid not in student_ids:
        return jsonify({"wrongs": None, "error": "응시 정보가 없습니다."})

    # 답안 키와 학생 답안 가져오기
    answer_key = get_answer_key_for_exam(exam)  # {1:3, 2:1, …}
    student_answers = get_student_answers_for_exam_and_id(exam, sid)
    if not student_answers:
        return jsonify({"wrongs": None, "error": "학생 답안을 찾을 수 없습니다."})

    wrongs = []
    for i, ans in enumerate(student_answers):
        qnum = i + 1
        correct = answer_key.get(qnum)
        if correct is None:
            continue  # 해당 문제번호가 키에 없으면 건너뜀
        # 비어있거나 숫자가 아니면 틀린 것으로 간주
        if not ans or not ans.isdigit() or int(ans) != correct:
            wrongs.append(qnum)

    return jsonify({"wrongs": wrongs})


@app.route("/api/submit_answer", methods=["POST"])
def api_submit_answer():
    """
    POST JSON: { exam:"{exam_name}", id:"{student_id}", question:int, answer:str }
    해당 문제의 정답 키와 비교해서 {correct: true/false, correctAnswer: X} 반환
    """
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


# ===============================================
#  메인 페이지 라우팅 (index.html을 리턴)
# ===============================================
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """
    어떤 경로에도 모두 index.html (싱글 페이지 애플리케이션) 을 리턴합니다.
    실제 정적 폴더 안의 파일을 요청할 때만 그 파일을 리턴하고,
    나머지는 index.html을 리턴하여 프론트엔드 라우팅 처리.
    """
    # 만약 static 내부 파일을 요청하면 해당 파일 그대로 리턴
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_file(os.path.join(app.static_folder, path))
    # 그 외에는 index.html
    return send_file(os.path.join(os.getcwd(), "index.html"))


# ===============================================
#  Flask 앱 실행
# ===============================================
if __name__ == "__main__":
    # 포트나 디버그 모드 등은 필요에 따라 수정하세요
    app.run(host="0.0.0.0", port=5000, debug=True)

