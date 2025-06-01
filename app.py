import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort
import pandas as pd

# ─── 기본 경로 설정 ─────────────────────────────────────────────
BASE_DIR          = Path(__file__).parent.resolve()
DATA_DIR          = BASE_DIR / 'data'
STUDENT_LIST_PATH = DATA_DIR / 'student_list.csv'
FRONTEND_DIR      = BASE_DIR / 'frontend'

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path='/'
)

# ─── 로그인 가능한 ID 로드 ─────────────────────────────────────────────
# student_list.csv에는 헤더 없이 첫 열에 리클래스ID만 쭉 나열된 형태라고 가정
student_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids  = set(student_df.iloc[:, 0].dropna().astype(str))

def authenticate(rid: str) -> bool:
    return rid in valid_ids


# ─── 각 시험 회차별 “응시 가능 ID 집합” 생성 ─────────────────────────────
#   - data/ 아래의 각 시험 폴더를 순회
#   - 각 exam_dir/student_answer/ 아래 모든 CSV를 읽어서 reclass_id 생성
#   - reclass_id = “이름” + “전화번호 끝 4자리” 형태로 저장
exam_ids: dict[str, set[str]] = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    student_ans_dir = exam_dir / 'student_answer'
    if not student_ans_dir.exists() or not student_ans_dir.is_dir():
        # student_answer가 없으면 응시자 없음으로 간주
        exam_ids[exam_dir.name] = set()
        continue

    ids: set[str] = set()
    # student_answer/ 밑의 모든 CSV 파일을 재귀적으로 읽어서 reclass_id 생성
    for csv_path in student_ans_dir.rglob('*.csv'):
        raw = pd.read_csv(csv_path, dtype=str)
        # CSV에 ‘이름’과 ‘전화번호’ 컬럼이 있다고 가정
        if '이름' in raw.columns and '전화번호' in raw.columns:
            df = raw.copy()
            df['phone4']     = df['전화번호'].str[-4:]
            df['reclass_id'] = df['이름'] + df['phone4']
            ids.update(df['reclass_id'].dropna().astype(str))
    exam_ids[exam_dir.name] = ids


# ─── 1) 첫 화면: index.html 서빙 ────────────────────────────────────────
@app.route('/')
def index():
    # 로그인 페이지를 포함한 모든 뷰를 index.html 하나로 제어
    return send_from_directory(str(FRONTEND_DIR), 'index.html')


# ─── 2) 로그인 인증 API ────────────────────────────────────────────────
@app.route('/api/authenticate')
def api_authenticate():
    """
    GET /api/authenticate?id=<리클래스ID>
    → valid_ids 집합에 있는지 확인
    """
    rid = request.args.get('id', '').strip()
    if not rid:
        return jsonify({'error': 'Missing id parameter'}), 400

    ok = authenticate(rid)
    return jsonify({'authenticated': ok}), (200 if ok else 401)


# ─── 3) 시험 회차 목록 가져오기 API ─────────────────────────────────────
@app.route('/api/exams')
def api_exams():
    """
    GET /api/exams
    → data/ 아래에 있는 모든 “student_answer” 폴더가 존재하는 디렉터리 이름을 반환
    """
    exams = []
    for d in DATA_DIR.iterdir():
        if d.is_dir() and (d / 'student_answer').exists():
            exams.append(d.name)
    return jsonify(exams)


# ─── 4) 해당 시험 회차에 현재 ID가 응시했는지 확인 API ─────────────────────
@app.route('/api/check_exam')
def api_check_exam():
    """
    GET /api/check_exam?exam=<examName>&id=<리클래스ID>
    → exam_ids[examName] 집합에 id가 있는지 확인
    """
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


# ─── 5) 성적표 URL 반환 API ────────────────────────────────────────────
@app.route('/api/reportcard')
def api_reportcard():
    """
    GET /api/reportcard?exam=<examName>&id=<리클래스ID>
    → data/<examName>/report card/ 하위에서 “<리클래스ID>_…_성적표.png”를 찾아 URL 반환
    """
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400

    exam_dir = DATA_DIR / exam / 'report card'
    if not exam_dir.exists() or not exam_dir.is_dir():
        return jsonify({'error': 'Report card 폴더가 없습니다.'}), 404

    # report card 폴더 안의 모든 PNG를 재귀 검색하여, 파일명에 rid가 포함된 첫 번째를 찾음
    for png_path in exam_dir.rglob('*.png'):
        if rid in png_path.name:
            # 웹에서 접근할 상대 경로를 만들어서 반환
            rel = png_path.relative_to(BASE_DIR)
            return jsonify({'url': '/' + str(rel).replace('\\','/')}), 200

    return jsonify({'error': 'Report card 파일을 찾을 수 없습니다.'}), 404


# ─── 6) 실제 성적표 이미지 서빙 라우트 ───────────────────────────────────
@app.route('/reportcard_file/<path:subpath>')
def reportcard_file(subpath):
    fullpath = BASE_DIR / subpath
    if not fullpath.exists():
        abort(404)
    return send_from_directory(str(fullpath.parent), fullpath.name)


# ─── 7) 앱 실행 설정 ────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
