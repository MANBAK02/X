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

# ─── 1) 인증용 학생 목록 로드 ───────────────────────
student_list_df = pd.read_csv(STUDENT_LIST_PATH, dtype=str)
valid_ids = set(student_list_df['reclass_id'])

# ─── 2) 시험 회차(폴더) 목록 및 S/CSV 로드 ────────────
all_exams: dict[str, pd.DataFrame] = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir() or exam_dir.name == 'student_list.csv':
        continue
    # exam_dir: data/<exam_name>/
    # S 폴더 안의 CSV를 합쳐서 DataFrame 생성
    frames = []
    for csv_path in (exam_dir / 'S').glob('*.csv'):
        df = pd.read_csv(csv_path, dtype=str)
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
        return jsonify({ 'error': 'Missing id parameter' }), 400
    if rid in valid_ids:
        return jsonify({ 'authenticated': True })
    else:
        return jsonify({ 'authenticated': False }), 401

@app.route('/api/exams')
def api_exams():
    """data/ 폴더 아래의 디렉터리 이름을 회차 목록으로 반환"""
    return jsonify(list(all_exams.keys()))

@app.route('/api/check_exam')
def api_check_exam():
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({ 'error': 'Missing parameters' }), 400
    if exam not in all_exams:
        return jsonify({ 'error': 'Unknown exam' }), 404

    df = all_exams[exam]
    if rid in set(df['reclass_id']):
        # 나중에 문제풀이 서비스로 리다이렉트 or 토큰 반환 등
        return jsonify({ 'registered': True })
    else:
        return jsonify({ 'registered': False, 'error': '해당 모의고사의 응시 정보가 없습니다.' }), 404

# 문제 이미지 등은 추후 구현
# @app.route('/problems/…')

# ─── 4) 앱 실행 ───────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
