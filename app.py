import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

# ─── 설정 ───────────────────────────────────
BASE_DIR          = Path(__file__).parent.resolve()
STUDENT_LIST_PATH = BASE_DIR / 'backend' / 'data' / 'student_list.csv'
EXAMS_DATA_DIR    = BASE_DIR / 'backend' / 'data' / 'S'
FRONTEND_DIR      = BASE_DIR / 'backend' / 'frontend'

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path='/'
)

# ─── 인증용 학생 목록 로드 ────────────────────
student_list_df = pd.read_csv(STUDENT_LIST_PATH, dtype=str)  
# student_list.csv 에는 최소 'reclass_id' 컬럼이 있어야 합니다.

def authenticate(reclass_id: str) -> bool:
    """ student_list.csv에 reclass_id가 있는지 확인 """
    return reclass_id in set(student_list_df['reclass_id'])

# ─── 모의고사 CSV 일괄 로드 & reclass_id 생성 ─────
def load_all_exams(s_dir: Path):
    exam_data: dict[str, list[pd.DataFrame]] = {}
    for csv_path in s_dir.rglob('*.csv'):
        exam_name = csv_path.parent.name       # e.g. “exam1”
        df = pd.read_csv(csv_path, dtype=str)  # 문자열로 읽기
        df['phone4']     = df['전화번호'].str[-4:]
        df['reclass_id'] = df['이름'] + df['phone4']
        exam_data.setdefault(exam_name, []).append(df)
    return {
        exam: pd.concat(dfs, ignore_index=True)
        for exam, dfs in exam_data.items()
    }

all_exams_df = load_all_exams(EXAMS_DATA_DIR)

# ─── 라우팅 ───────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

@app.route('/api/score')
def get_score():
    exam       = request.args.get('exam', '').strip()
    reclass_id = request.args.get('id', '').strip()

    # 1) 파라미터 검사
    if not exam or not reclass_id:
        return jsonify({'error': 'Missing exam or id parameter'}), 400

    # 2) 로그인 인증
    if not authenticate(reclass_id):
        return jsonify({'error': 'Unauthorized'}), 401

    # 3) 존재하는 exam인지 확인
    if exam not in all_exams_df:
        return jsonify({'error': 'Unknown exam'}), 404

    # 4) 점수 조회
    df  = all_exams_df[exam]
    rec = df[df['reclass_id'] == reclass_id]
    if rec.empty:
        return jsonify({'error': 'Not found'}), 404

    return jsonify(rec.iloc[0].to_dict())

# ─── 실행 ─────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
