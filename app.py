import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
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
# 첫 열에 ID가 쭉 나열되어 있다고 가정 (헤더 없이 읽기)
student_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids  = set(student_df.iloc[:, 0].dropna().astype(str))

def authenticate(rid: str) -> bool:
    return rid in valid_ids

# ─── 2) 시험별 S.CSV 읽어 응시 가능한 ID 집합 생성 ────
exam_ids: dict[str, set[str]] = {}

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    s_file = exam_dir / 'S.CSV'
    if not s_file.exists():
        continue

    # CSV에 헤더가 있는 경우 자동 감지, 없으면 첫 행이 컬럼명이 됨
    df = pd.read_csv(s_file, dtype=str)

    # 이름 컬럼이 '이름' 이 아니면 첫 컬럼으로 대체
    name_col = '이름' if '이름' in df.columns else df.columns[0]
    # 전화번호 컬럼이 '전화번호' 가 아니면 두 번째 컬럼으로 대체
    phone_col = '전화번호' if '전화번호' in df.columns else df.columns[1]

    # reclass_id 생성
    df['phone4']     = df[phone_col].str[-4:]
    df['reclass_id'] = df[name_col] + df['phone4']

    exam_ids[exam_dir.name] = set(df['reclass_id'].dropna().astype(str))

# ─── 3) 라우팅 ───────────────────────────────────────
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
    """data/ 폴더 아래 시험 디렉터리 이름(회차) 목록 반환"""
    return jsonify(list(exam_ids.keys()))

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

# ─── 4) 앱 실행 ─────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
