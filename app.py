# app.py
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

# ─── 1) 인증용 학생 목록 로드(헤더 없이) ─────────────────
# header=None으로 읽어서 0번 컬럼 전체를 ID로 취급
student_list_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids = set(student_list_df.iloc[:, 0].dropna().astype(str))

def authenticate(reclass_id: str) -> bool:
    return reclass_id in valid_ids

# ─── 2) 시험 회차(폴더) 목록 및 데이터 로드 ────────────
all_exams: dict[str, pd.DataFrame] = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir() or not (exam_dir / 'S').is_dir():
        continue

    frames = []
    for csv_path in (exam_dir / 'S').glob('*.csv'):
        df = pd.read_csv(csv_path, dtype=str)
        # '이름'과 '전화번호' 컬럼을 그대로 쓴다면:
        df['phone4']     = df['전화번호'].str[-4:]
        df['reclass_id'] = df['이름'] + df['phone4']
        frames.append(df)
    all_exams[exam_dir.name] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# ─── 3) 라우트 정의 ─────────────────────────────────
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
    """ data/ 폴더 아래 시험 디렉터리 이름 목록 반환 """
    return jsonify(list(all_exams.keys()))

@app.route('/api/check_exam')
def api_check_exam():
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400
    if exam not in all_exams:
        return jsonify({'error': 'Unknown exam'}), 404

    df = all_exams[exam]
    registered = (df['reclass_id'] == rid).any()
    status = 200 if registered else 404
    return jsonify({
        'registered': registered,
        'error': None if registered else '해당 모의고사의 응시 정보가 없습니다.'
    }), status

# ─── 4) 앱 실행 ───────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
