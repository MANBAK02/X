# app.py
import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
import pandas as pd

# ─── 기본 경로 설정 ─────────────────────────────────
BASE_DIR          = Path(__file__).parent.resolve()
DATA_DIR          = BASE_DIR / 'data'
STUDENT_LIST_PATH = DATA_DIR / 'student_list.csv'
FRONTEND_DIR      = BASE_DIR / 'frontend'

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path='/'
)

# ─── 1) student_list.csv 에서 로그인 허용 ID 집합 로드 ────
student_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids  = set(student_df.iloc[:, 0].dropna().astype(str))

def authenticate(rid: str) -> bool:
    return rid in valid_ids

# ─── 2) 각 시험별 student_answer/*.csv 읽어 응시 가능한 ID 집합 생성 ────
exam_ids: dict[str, set[str]] = {}

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    answer_dir = exam_dir / 'student_answer'
    ids: set[str] = set()
    if answer_dir.is_dir():
        for csv_path in answer_dir.glob('*.csv'):
            df = pd.read_csv(csv_path, dtype=str)
            # 이름 컬럼 자동 감지
            name_col = '이름' if '이름' in df.columns else df.columns[0]
            # 전화번호 컬럼 자동 감지
            phone_col = '전화번호' if '전화번호' in df.columns else df.columns[1]

            df['phone4']     = df[phone_col].str[-4:]
            df['reclass_id'] = df[name_col] + df['phone4']
            ids.update(df['reclass_id'].dropna().astype(str))
    exam_ids[exam_dir.name] = ids

# ─── 3) 라우팅 ─────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

@app.route('/api/authenticate')
def api_authenticate():
    rid = request.args.get('id', '').strip()
    if not rid:
        return jsonify({'error': 'Missing id parameter'}), 400
    ok = authenticate(rid)
    return jsonify({'authenticated': ok}), (200 if ok else 401)

@app.route('/api/exams')
def api_exams():
    # 데이터 디렉터리 바로 아래의 모든 시험 폴더 이름 반환
    exams = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]
    return jsonify(exams)

@app.route('/api/check_exam')
def api_check_exam():
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400
    if exam not in exam_ids:
        return jsonify({'error': 'Unknown exam'}), 404

    registered = rid in exam_ids[exam]
    status     = 200 if registered else 404
    return jsonify({
        'registered': registered,
        'error':      None if registered else '해당 모의고사의 응시 정보가 없습니다.'
    }), status

@app.route('/report')
def api_report():
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400

    report_dir = DATA_DIR / exam / 'report card'
    if not report_dir.is_dir():
        return jsonify({'error': 'Report not found'}), 404

    # "{rid}_{exam}_..._성적표.png" 형태 파일 찾기
    for fname in report_dir.iterdir():
        if (fname.is_file()
         and fname.name.startswith(f"{rid}_{exam}_")
         and fname.name.endswith("_성적표.png")):
            return send_file(str(fname), mimetype='image/png')

    return jsonify({'error': 'Report not found'}), 404

# ─── 4) 앱 실행 ─────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
