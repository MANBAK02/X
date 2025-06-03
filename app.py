# app.py
import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR          = Path(__file__).parent.resolve()
DATA_DIR          = BASE_DIR / 'data'
STUDENT_LIST_PATH = DATA_DIR / 'student_list.csv'
FRONTEND_DIR      = BASE_DIR / 'frontend'

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path='/'
)

# ─── 1) student_list.csv 에서 로그인 허용 ID 집합 로드 ─────────────
# header=None 으로 읽어서 첫 열(학생 리클래스 ID)만 valid_ids 로 사용
import pandas as pd
student_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids  = set(student_df.iloc[:, 0].dropna().astype(str))

def authenticate(rid: str) -> bool:
    return rid in valid_ids

# ─── 2) 시험별 answer/S 폴더를 읽어 응시 가능한 ID 집합 생성 ─────────
exam_ids = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    # student_answer 폴더 안에 있는 CSV들의 첫열(리클래스 ID)을 모아둠
    ans_dir = exam_dir / 'student_answer'
    if not ans_dir.is_dir():
        continue

    ids = set()
    for csv_path in ans_dir.glob('*.csv'):
        # header=None 으로 읽으면 첫 열이 학생 리클래스 ID라 가정
        df = pd.read_csv(csv_path, header=None, dtype=str)
        ids.update(df.iloc[:, 0].dropna().astype(str))
    exam_ids[exam_dir.name] = ids

# ─── 3) 라우팅 ──────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

@app.route('/icons/<path:filename>')
def serve_icon(filename):
    # 예: /icons/home.svg → frontend/icons/home.svg
    return send_from_directory(str(FRONTEND_DIR / 'icons'), filename)

@app.route('/api/authenticate')
def api_authenticate():
    rid = request.args.get('id', '').strip()
    if not rid:
        return jsonify({'error': 'Missing id parameter'}), 400
    ok = authenticate(rid)
    return jsonify({'authenticated': ok}), (200 if ok else 401)

@app.route('/api/exams')
def api_exams():
    # data/ 폴더 바로 아래 있는 디렉토리 이름(시험 회차) 리스트 반환
    exams = sorted([d.name for d in DATA_DIR.iterdir() if d.is_dir()])
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

@app.route('/api/reportcard')
def api_reportcard():
    """
    요청 예시: /api/reportcard?exam=Spurt 모의고사 08회&id=홍길동6123
    → data/<exam>/report card/**/*_성적표.png 를 재귀 탐색하며
      '[rid]_[exam]_성적표.png' 같은 파일을 찾아서 URL로 응답
    """
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400

    # 시험 폴더가 존재하는지 확인
    exam_dir = DATA_DIR / exam
    if not exam_dir.exists() or not exam_dir.is_dir():
        return jsonify({'error': 'Unknown exam'}), 404

    report_root = exam_dir / 'report card'
    if not report_root.exists() or not report_root.is_dir():
        return jsonify({'error': 'Report card 폴더가 없습니다.'}), 404

    # 재귀 탐색 검색
    found_url = None
    for root, dirs, files in os.walk(report_root):
        for fname in files:
            # 파일명에 rid, exam, 그리고 '성적표' 키워드가 포함되어 있어야 한다면
            # 예: "홍길동6123_Spurt 모의고사 08회_성적표.png"
            if rid in fname and exam in fname and '성적표' in fname:
                rel_path = Path(root) / fname
                # 클라이언트가 접근할 수 있도록 절대 경로 → 상대 URL로 바꾸기
                # 예: report_root = 'data/Spurt 모의고사 08회/report card'
                # 실제 파일 시스템: BASE_DIR/data/Spurt 모의고사 08회/report card/홍길동…png
                # 우리는 이걸 send_from_directory 로 보내줄 예정
                found_dir = str(Path(root).resolve())
                found_file = fname
                found_url = (found_dir, found_file)
                break
        if found_url:
            break

    if not found_url:
        return jsonify({'error': '해당 모의고사의 성적표를 찾을 수 없습니다.'}), 404

    # send_from_directory 에서는 절대 경로를 넣어도 되지만,
    # 보안을 위해 실제로는 `BASE_DIR` 기준 하위 디렉터리여야 합니다.
    # 경로가 정확하다면:
    directory, filename = found_url
    # 클라이언트가 이미지 자체를 곧바로 볼 수 있도록 URL 형식으로 리턴
    # 예: "/reportcard_image?dir=/abs/path/to/…&file=홍길동…png"
    # 하지만 간단히 send_from_directory를 직접 호출해도 된다면:
    return send_from_directory(directory, filename)

# ─── 4) 앱 실행(Waitress 사용이 아니라, Railway Start Command에서 waitress-serve 사용) ─────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
