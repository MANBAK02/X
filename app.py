import os
import csv
from flask import Flask, jsonify, request, send_from_directory, abort

app = Flask(
    __name__,
    static_folder="frontend",   # 프론트엔드 정적 파일(index.html, globe.gif, icons 등)을 이 폴더에서 서빙
    static_url_path=""          # "/static" 없이 바로 루트에서 접근
)

# ──────────────────────────────────────────────────────────────────────────
#  설정값
# ──────────────────────────────────────────────────────────────────────────

# 데이터가 저장된 루트 디렉터리 (exam별, student_list.csv, report card 등)
BASE_DIR = os.path.join(os.getcwd(), "data")

# 학생 전체 목록(CSV) 경로: data/student_list.csv
STUDENT_LIST_PATH = os.path.join(BASE_DIR, "student_list.csv")


# ──────────────────────────────────────────────────────────────────────────
#  유틸리티 함수들
# ──────────────────────────────────────────────────────────────────────────

def load_all_valid_ids():
    """
    data/student_list.csv 의 첫 열(리클래스 ID)만 읽어서 리스트로 리턴
    - CSV 헤더가 없다고 가정. 첫 번째 행부터 바로 ID가 나열되어 있음.
    """
    valid_ids = set()
    if not os.path.isfile(STUDENT_LIST_PATH):
        return valid_ids

    with open(STUDENT_LIST_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            rid = row[0].strip()
            if rid:
                valid_ids.add(rid)
    return valid_ids


def find_student_in_exam(exam_name, student_id):
    """
    특정 exam 디렉터리 내의 student_answer 폴더를 순회하며,
    로그인된 student_id(리클래스 ID)가 존재하는지 검사.
    student_answer 안의 각 CSV 파일마다:
      첫 번째 열 = 이름, 두 번째 열 = 전화번호(하이픈 포함 가능)
      → 전화번호의 마지막 8자리(ex: "12345678")를 추출하여 '이름' + '마지막8자리' 가 student_id와 같으면 응시자로 간주
    """
    exam_dir = os.path.join(BASE_DIR, exam_name)
    sa_folder = os.path.join(exam_dir, "student_answer")
    if not os.path.isdir(sa_folder):
        return False

    for fname in os.listdir(sa_folder):
        if not fname.lower().endswith(".csv"):
            continue
        fpath = os.path.join(sa_folder, fname)
        try:
            with open(fpath, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2:
                        continue
                    name = row[0].strip()
                    phone = row[1].strip()
                    # 전화번호에서 숫자만 남기고, 마지막 8자리 추출
                    digits = "".join(filter(str.isdigit, phone))
                    if len(digits) < 8:
                        continue
                    suffix8 = digits[-8:]
                    generated_id = f"{name}{suffix8}"
                    if generated_id == student_id:
                        return True
        except Exception:
            # CSV 읽는 중 문제가 생겨도 계속 다음 파일 시도
            continue

    return False


def find_report_filename(exam_name, student_id):
    """
    data/{exam_name}/report card 폴더 전체(서브폴더 포함)를 재귀 탐색하여,
    'student_id'로 시작하고 '.png'로 끝나는 파일명 하나를 찾아서 리턴.
    """
    exam_dir = os.path.join(BASE_DIR, exam_name)
    rc_root = os.path.join(exam_dir, "report card")
    if not os.path.isdir(rc_root):
        return None

    # os.walk 를 통해 서브폴더까지 모두 순회
    for dirpath, dirnames, filenames in os.walk(rc_root):
        for fname in filenames:
            lower = fname.lower()
            if lower.startswith(student_id.lower()) and lower.endswith(".png"):
                # 찾은 경우, 해당 디렉터리 기준으로 상대 경로를 만들어서 리턴
                rel_dir = os.path.relpath(dirpath, rc_root)
                if rel_dir == ".":
                    return fname
                else:
                    # 예: "A반" 서브폴더 아래에 있으면 "A반/파일명.png" 형태로 리턴
                    return os.path.join(rel_dir, fname)
    return None


# ──────────────────────────────────────────────────────────────────────────
#  API 엔드포인트들
# ──────────────────────────────────────────────────────────────────────────

@app.route("/api/authenticate")
def api_authenticate():
    """
    로그인 시 호출 (GET): /api/authenticate?id={리클래스ID}
    → student_list.csv 에서 해당 ID가 존재하는지 확인
    """
    sid = request.args.get("id", "").strip()
    if not sid:
        return jsonify({"authenticated": False, "error": "ID를 입력하세요"}), 400

    valid_ids = load_all_valid_ids()
    if sid in valid_ids:
        return jsonify({"authenticated": True})
    else:
        return jsonify({"authenticated": False, "error": "인증되지 않은 ID입니다"}), 200


@app.route("/api/exams")
def api_exams():
    """
    회차 목록 요청 (GET): /api/exams
    → data/ 폴더 내의 하위 디렉터리명을 배열로 리턴
    """
    exams = []
    if not os.path.isdir(BASE_DIR):
        return jsonify([])

    for name in sorted(os.listdir(BASE_DIR)):
        path = os.path.join(BASE_DIR, name)
        # 디렉터리이면서 student_list.csv가 아닌 것들만 회차로 간주
        if os.path.isdir(path) and name != "student_list.csv":
            exams.append(name)
    return jsonify(exams)


@app.route("/api/check_exam")
def api_check_exam():
    """
    회차 선택 후 응시 여부 확인 (GET): /api/check_exam?exam={exam_name}&id={리클래스ID}
    → data/{exam_name}/student_answer 폴더 내를 순회하여 해당 ID가 있는지 검사
    """
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"registered": False, "error": "파라미터가 잘못되었습니다."}), 400

    if find_student_in_exam(exam, sid):
        return jsonify({"registered": True})
    else:
        return jsonify({"registered": False, "error": "응시 정보가 없습니다."}), 200


@app.route("/api/reportcard")
def api_reportcard():
    """
    성적표 요청 (GET): /api/reportcard?exam={exam_name}&id={리클래스ID}
    → data/{exam_name}/report card/*(서브폴더 포함) 경로에서 "{리클래스ID}_..._성적표.png" 를 찾아서 URL 리턴
    """
    exam = request.args.get("exam", "").strip()
    sid = request.args.get("id", "").strip()
    if not exam or not sid:
        return jsonify({"url": None, "error": "파라미터가 잘못되었습니다."}), 400

    rel_path = find_report_filename(exam, sid)
    if rel_path:
        # rel_path 가 "A반/파일명.png" 혹은 "파일명.png" 형태로 리턴되므로,
        # 클라이언트는 /report/{exam}/{rel_path} 로 요청하면 된다.
        return jsonify({"url": f"/report/{exam}/{rel_path.replace(os.sep, '/')}"} )
    else:
        return jsonify({"url": None, "error": "성적표를 찾을 수 없습니다."})


@app.route("/report/<path:exam>/<path:subpath>")
def serve_report_image(exam, subpath):
    """
    report card 이미지를 클라이언트에 서빙
    URL 예: /report/Spurt 모의고사 07회/A반/강민엽1553_Spurt 모의고사 07회_성적표.png
    """
    # subpath 에는 "A반/파일명.png" 혹은 "파일명.png" 와 같이 전달됨
    report_root = os.path.join(BASE_DIR, exam, "report card")
    requested = os.path.normpath(os.path.join(report_root, subpath))
    # 경로가 report_root 밖으로 나가는 시도를 막기 위해 체크
    if not requested.startswith(os.path.normpath(report_root) + os.sep) and requested != os.path.normpath(report_root):
        abort(404)

    if not os.path.isfile(requested):
        abort(404)

    # 실제로는 send_from_directory 에 report_root와 subpath(파일명 혹은 "A반/파일명")를 넘기면 됨
    # send_from_directory 는 디렉터리와 파일명을 두 번째 인자로 받기 때문에,
    # 서브폴더까지 포함된 경우 경로 분할이 필요함.
    dir_part, file_part = os.path.split(requested)
    return send_from_directory(dir_part, file_part)


# ──────────────────────────────────────────────────────────────────────────
#  모든 비-API 요청은 index.html → SPA(싱글 페이지)로 연결
# ──────────────────────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """
    프론트엔드 정적 자산을 먼저 시도하고, 아니면 index.html (싱글 페이지)
    """
    static_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(static_path) and not os.path.isdir(static_path):
        # 예: "icons/home.png" → 바로 반환
        return send_from_directory(app.static_folder, path)
    else:
        # 루트 요청 혹은 SPA의 나머지 경로 → index.html
        return send_from_directory(app.static_folder, "index.html")


# ──────────────────────────────────────────────────────────────────────────
#  앱 실행
# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 로컬에서 테스트할 때: debug=True 로 찍으면 콘솔에 에러 로그가 더 잘 보입니다.
    app.run(host="0.0.0.0", port=8080, debug=True)
