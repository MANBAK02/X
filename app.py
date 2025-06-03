import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
import pandas as pd

app = Flask(
    __name__,
    static_folder='frontend',
    static_url_path='/'
)

# ┌───────────────────────────────────────────────────
# │ 1) 인증용 ID 목록 로드
# └───────────────────────────────────────────────────
DATA_DIR = Path('data')
STUDENT_LIST_CSV = DATA_DIR / 'student_list.csv'

valid_ids = set()
if STUDENT_LIST_CSV.exists():
    df_student_list = pd.read_csv(STUDENT_LIST_CSV, header=None, dtype=str)
    for val in df_student_list.iloc[:, 0].dropna().astype(str):
        valid_ids.add(val.strip())
    print(f"[DEBUG] 인증 가능한 ID 총 {len(valid_ids)}개 로드됨.")
else:
    print("[WARN] data/student_list.csv 파일이 존재하지 않습니다.")

# ┌───────────────────────────────────────────────────
# │ 2) 시험별 응시자 ID 집합 생성 (case-insensitive *.csv)
# └───────────────────────────────────────────────────
exam_ids = {}

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    student_ans_dir = exam_dir / 'student_answer'
    ids_for_this_exam = set()

    if student_ans_dir.is_dir():
        # ─ 대소문자 구분 없이 CSV 파일 매칭 ─
        for pattern in ('*.csv', '*.CSV'):
            for csv_path in student_ans_dir.glob(pattern):
                try:
                    # header=None: 첫 번째 열이 이름, 두 번째 열이 전화번호(8자리)
                    df_ans = pd.read_csv(csv_path, dtype=str, header=None)
                except Exception as e:
                    print(f"[WARN] {csv_path} 읽는 중 오류: {e}")
                    continue

                for row in df_ans.itertuples(index=False):
                    name = str(row[0]).strip() if len(row) >= 1 else ''
                    phone8 = str(row[1]).strip() if len(row) >= 2 else ''
                    if len(phone8) >= 4:
                        reclass_id = name + phone8[-4:]
                        ids_for_this_exam.add(reclass_id)

    if ids_for_this_exam:
        exam_ids[exam_dir.name] = ids_for_this_exam
        print(f"[DEBUG] Exam '{exam_dir.name}' → 응시자 리클래스 ID: {len(ids_for_this_exam)}개")
    else:
        print(f"[DEBUG] Exam '{exam_dir.name}' → student_answer 폴더가 없거나, ID 생성 불가")

# ┌───────────────────────────────────────────────────
# │ 3) Flask API 엔드포인트 정의
# └───────────────────────────────────────────────────

@app.route('/api/authenticate')
def api_authenticate():
    user_id = request.args.get('id', '').strip()
    if user_id in valid_ids:
        return jsonify(authenticated=True)
    else:
        return jsonify(authenticated=False)

@app.route('/api/exams')
def api_get_exams():
    return jsonify(sorted(exam_ids.keys()))

@app.route('/api/check_exam')
def api_check_exam():
    user_id = request.args.get('id', '').strip()
    exam = request.args.get('exam', '').strip()

    if exam not in exam_ids:
        return jsonify(registered=False, error='존재하지 않는 회차입니다.')
    if user_id in exam_ids[exam]:
        return jsonify(registered=True)
    else:
        return jsonify(registered=False, error='해당 모의고사의 응시 정보가 없습니다.')

@app.route('/api/reportcard')
def api_reportcard():
    user_id = request.args.get('id', '').strip()
    exam = request.args.get('exam', '').strip()

    exam_dir = DATA_DIR / exam
    if not exam_dir.is_dir():
        return jsonify(error='존재하지 않는 시험 회차입니다.')

    report_dir = exam_dir / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.')

    # report card 하위에 반별 폴더가 있고 그 안에 PNG가 있는 경우 재귀 탐색
    for img_path in report_dir.rglob(f'*{user_id}*.png'):
        # report_dir 기준으로 상대 경로를 뽑아두고
        rel_path = img_path.relative_to(report_dir)
        # URL 상으로는 하위 폴더 구조까지 포함해서 클라이언트에 알려준다
        url = f'/report/{exam}/{rel_path.as_posix()}'
        return jsonify(url=url)

    return jsonify(error='성적표를 찾을 수 없습니다.')

# “/report/<exam>/<path:...>”를 받아서 report card 하위 디렉터리로 매핑
@app.route('/report/<exam>/<path:subpath>')
def send_report(exam, subpath):
    report_folder = DATA_DIR / exam / 'report card'
    # subpath가 e.g. "한반/강민엽1553_성적표.png" 형태로 들어온다.
    return send_from_directory(report_folder, subpath)

# ┌───────────────────────────────────────────────────
# │ 4) SPA 정적 파일 서빙
# └───────────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = Path(app.static_folder)
    requested = static_dir / path

    if path != "" and requested.exists():
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
