# app.py
import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort
import pandas as pd

app = Flask(__name__, static_folder='frontend', static_url_path='/')


# ─── 기본 경로 설정 ─────────────────────────────────────────
BASE_DIR          = Path(__file__).parent.resolve()
DATA_DIR          = BASE_DIR / 'data'
STUDENT_LIST_PATH = DATA_DIR / 'student_list.csv'
FRONTEND_DIR      = BASE_DIR / 'frontend'


# ─── 1) student_list.csv 에서 로그인 허용 ID 집합 로드 ─────────────────
try:
    # header=None: 첫 열 전체를 ID 목록으로 취급
    student_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
    valid_ids  = set(student_df.iloc[:, 0].dropna().astype(str))
except Exception:
    valid_ids = set()

def authenticate(rid: str) -> bool:
    """ student_list.csv 첫 열에 있는 ID면 True """
    return rid in valid_ids


# ─── 2) 각 시험 폴더 안의 student_answer/ 하위 모든 CSV를 읽어 응시 가능한 ID 집합 생성 ──────
exam_ids = {}     # { exam_name: {rid1, rid2, ...}, ... }
exam_files = {}   # { exam_name: [Path1, Path2, ...] } → answer/ 밑 CSV 목록

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    # 2-1) “answer” 폴더로 간주
    answer_dir = exam_dir / 'answer'
    if not answer_dir.exists() or not answer_dir.is_dir():
        # answer/ 폴더가 없으면 이 exam_dir는 회차로 인정하지 않음
        continue

    # 2-2) answer/ 폴더 하위의 모든 CSV 파일 경로 수집
    csv_list = list(answer_dir.rglob('*.csv'))
    if not csv_list:
        # CSV 파일이 하나도 없으면 회차로 인정하지 않음
        continue

    # exam_files에 저장(향후 메타정보로 사용 가능)
    exam_files[exam_dir.name] = csv_list

    # 2-3) 응시 가능한 ID 집합 생성 (이름+전화끝4자리)
    ids = set()
    for csv_path in csv_list:
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except Exception:
            continue

        # “이름”과 “전화번호” 컬럼이 있으면 → reclass_id = 이름 + 전화끝4
        if '이름' in df.columns and '전화번호' in df.columns:
            names  = df['이름'].astype(str)
            phones = df['전화번호'].astype(str).str[-4:]
            temp_ids = (names + phones).tolist()
            ids.update(temp_ids)
        else:
            # “이름/전화번호” 칼럼 조합이 없으면 → 첫 번째 컬럼을 ID로 간주
            ids.update(df.iloc[:, 0].dropna().astype(str).tolist())

    exam_ids[exam_dir.name] = ids


# ─── 3) 라우팅 ──────────────────────────────────────────────────

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
    """
    data/ 폴더 아래, 
    ‒ “answer” 폴더가 존재하고 
    ‒ 그 안에 *.csv 파일이 한 개 이상 있어야 하는 
    시험 디렉터리 이름 목록을 반환
    """
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


# ─── 4) /report 라우트: “report card” 폴더에서 학생 성적표 이미지만 엄격 매칭 ───────────
@app.route('/report')
def report_view():
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return abort(400, description="Missing parameters")

    # report card 폴더 경로
    report_root = DATA_DIR / exam / 'report card'
    if not report_root.exists() or not report_root.is_dir():
        return abort(404, description="Report card 폴더가 없습니다.")

    # 파일명 패턴: "{rid}_{exam}_…_성적표.png" → 엄격 매칭
    pattern_prefix = f"{rid}_{exam}_"
    matched_file = None

    for png_path in report_root.rglob('*.png'):
        fname = png_path.name
        if fname.startswith(pattern_prefix) and fname.endswith('_성적표.png'):
            matched_file = png_path
            break

    if not matched_file:
        return abort(404, description="Report not found")

    # HTML 템플릿으로 렌더링 (서브 페이지에도 홈 버튼 포함)
    rel_path = matched_file.relative_to(BASE_DIR)  
    html = f"""
    <!DOCTYPE html>
    <html lang='ko'>
    <head>
      <meta charset='utf-8'>
      <meta name='viewport' content='width=device-width, initial-scale=1'>
      <title>내 성적표</title>
      <style>
        body {{
          margin: 0; padding: 1rem;
          font-family: sans-serif; background: #f9f9f9;
        }}
        .container {{
          max-width: 600px; width: 100%;
          margin: 0 auto; background: white;
          padding: 2rem; min-height: 800px;
          border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
          position: relative;
        }}
        .home-btn {{
          position: absolute; top: 1rem; left: 1rem;
          display: flex; align-items: center;
          text-decoration: none; color: #333; font-size: 1rem;
        }}
        .home-btn img {{
          width: 16px; height: 16px; margin-right: 0.25rem;
        }}
        .report-img {{
          display: block; max-width: 100%;
          height: auto; margin: 2rem auto;
        }}
      </style>
    </head>
    <body>
      <div class='container'>
        <!-- 서브 페이지에서도 홈 버튼 보이기 -->
        <a href='/' class='home-btn'>
          <img src='/icons/home.svg' alt='Home Icon'>
          <span>처음으로</span>
        </a>
        <h1>내 성적표</h1>
        <img src='/{rel_path.as_posix()}' alt='Report Card' class='report-img'>
      </div>
    </body>
    </html>
    """
    return html


# ─── 5) static 파일: icons 디렉터리 및 data 내 이미지/CSV도 제공 ──────────────
@app.route('/icons/<path:filename>')
def serve_icon(filename):
    return send_from_directory(str(FRONTEND_DIR / 'icons'), filename)

@app.route('/data/<path:filename>')
def serve_data_files(filename):
    # report HTML이 img src='data/...png' 형태로 요청할 때 사용
    return send_from_directory(str(BASE_DIR), filename)


# ─── 6) 앱 실행 (Waitress WSGI 서버) ─────────────────────────────────────────
if __name__ == '__main__':
    import waitress
    port = int(os.environ.get('PORT', 5000))
    waitress.serve(app, host='0.0.0.0', port=port)

