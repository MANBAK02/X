import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request, abort

app = Flask(
    __name__,
    static_folder=str(Path(__file__).parent / "frontend"),
    static_url_path=""
)

BASE_DIR = Path(__file__).parent
EXAMS_DIR = BASE_DIR / "exams"               # 시험 데이터 최상위
STUDENT_LIST_CSV = BASE_DIR / "student_list.csv"

# 1) 로그인 가능한 ID 로드
def load_student_list():
    ids = set()
    if STUDENT_LIST_CSV.exists():
        import csv
        with open(STUDENT_LIST_CSV, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    ids.add(row[0].strip())
    return ids

VALID_IDS = load_student_list()

@app.route("/api/authenticate")
def authenticate():
    _id = request.args.get("id", "").strip()
    return jsonify(authenticated=_id in VALID_IDS)

# student_ids 집합 로딩 직후
print("Loaded student IDs sample:", list(student_ids)[:10])
print("Total IDs loaded:", len(student_ids))


# 2) 회차 목록
@app.route("/api/exams")
def list_exams():
    if not EXAMS_DIR.exists():
        return jsonify([])
    exams = [d.name for d in EXAMS_DIR.iterdir() if d.is_dir()]
    return jsonify(sorted(exams))

# 3) 응시 여부 확인 (student_answer 하위 전체 검색)
@app.route("/api/check_exam")
def check_exam():
    exam = request.args.get("exam", "")
    user_id = request.args.get("id", "").strip()
    dir_sa = EXAMS_DIR / exam / "student_answer"
    if not dir_sa.exists():
        return jsonify(registered=False, error="응시 정보가 없습니다")

    found = False
    import csv
    for root, _, files in os.walk(dir_sa):
        for fn in files:
            if fn.lower().endswith(".csv"):
                path = Path(root) / fn
                with open(path, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) < 2:
                            continue
                        name = row[0].strip()
                        phone = row[1].strip().replace("-", "")
                        sid = f"{name}{phone}"
                        if sid == user_id:
                            found = True
                            break
                if found:
                    break
        if found:
            break

    return jsonify(registered=found, error=None if found else "응시 정보가 없습니다")

# 4) 성적표 URL 반환 (report_card 하위 전체 검색)
@app.route("/api/reportcard")
def report_card():
    exam = request.args.get("exam", "")
    user_id = request.args.get("id", "").strip()
    dir_rc = EXAMS_DIR / exam / "report card"
    if not dir_rc.exists():
        return jsonify(url=None, error="성적표를 찾을 수 없습니다.")

    rc_url = None
    for root, _, files in os.walk(dir_rc):
        for fn in files:
            # PNG, JPG 등 원하는 확장자 모두 허용
            if fn.lower().endswith((".png", ".jpg", ".jpeg")):
                if fn.startswith(user_id + "_"):
                    rel = Path(root).relative_to(BASE_DIR / "frontend")
                    rc_url = f"/{rel.as_posix()}/{fn}"
                    break
        if rc_url:
            break

    if rc_url:
        return jsonify(url=rc_url)
    else:
        return jsonify(url=None, error="성적표를 찾을 수 없습니다.")

# 5) 정적 파일 서빙 (index.html, icons, globe.gif 등)
@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_frontend(path):
    full = Path(app.static_folder) / path
    if not full.exists():
        abort(404)
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

