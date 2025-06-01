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
    static_folder=str(FRONTEND_DIR),     # frontend 디렉터리를 정적 파일 루트로 사용
    static_url_path='/'                   # “/” 경로로 접근 시 정적 파일을 제공
)

# ─── 1) student_list.csv 에서 로그인 허용 ID 집합 로드 ────────────────
# header=None 으로 읽어서 첫 번째 열 전체를 ID로 취급
student_list_df = pd.read_csv(STUDENT_LIST_PATH, header=None, dtype=str)
valid_ids = set(student_list_df.iloc[:, 0].dropna().astype(str))

def authenticate(rid: str) -> bool:
    """data/student_list.csv 첫 열에 있는 ID면 True, 아니면 False"""
    return rid in valid_ids

# ─── 2) 각 시험별 ‘answer/’ 폴더를 읽어 시험 정보(회차) 로드 ────────────
# exam_info: { 시험명: DataFrame(시험 회차별 정보 합쳐진) }
exam_info: dict[str, pd.DataFrame] = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue
    # “answer” 폴더 하위의 모든 *.csv를 찾아서, 회차 정보 DataFrame으로 합칩니다.
    answer_dir = exam_dir / 'answer'
    if not answer_dir.is_dir():
        # 만약 answer 폴더가 없으면 빈 DataFrame으로 두되, 회차 이름만 인식되도록 처리
        exam_info[exam_dir.name] = pd.DataFrame()
        continue

    frames = []
    for csv_path in answer_dir.rglob('*.csv'):
        try:
            df_tmp = pd.read_csv(csv_path, dtype=str)
            frames.append(df_tmp)
        except Exception:
            # CSV 읽기 오류가 나면 해당 파일 무시
            continue
    if frames:
        exam_info[exam_dir.name] = pd.concat(frames, ignore_index=True)
    else:
        exam_info[exam_dir.name] = pd.DataFrame()

# ─── 3) 각 시험별 ‘student_answer/’ 폴더 하위에서 응시 ID 집합 생성 ─────────
exam_ids: dict[str, set[str]] = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    s_dir = exam_dir / 'student_answer'
    ids = set()
    if s_dir.is_dir():
        # s_dir 하위 모든 *.csv 탐색
        for csv_path in s_dir.rglob('*.csv'):
            try:
                raw = pd.read_csv(csv_path, dtype=str)
            except Exception:
                continue

            # ① 컬럼명이 '성명'인지, 그렇지 않으면 첫 번째 컬럼을 이름으로 사용
            if '성명' in raw.columns:
                name_col = '성명'
            else:
                name_col = raw.columns[0]

            # ② 컬럼명이 '전화번호'인지, 그렇지 않으면 두 번째 컬럼을 전화번호로 사용
            if '전화번호' in raw.columns:
                phone_col = '전화번호'
            else:
                phone_col = raw.columns[1]

            # 전화번호 끝 4자리 추출
            # (이미 “010-1234-7860”처럼 하이픈이 포함돼 있더라도 마지막 4글자는 추출됨)
            raw['phone4'] = raw[phone_col].astype(str).str.replace(r'\D', '', regex=True).str[-4:]
            # reclass_id = “이름” + “phone4”
            raw['reclass_id'] = raw[name_col].astype(str) + raw['phone4']

            ids.update(raw['reclass_id'].dropna().astype(str))
    # 시험명: 응시 ID 집합
    exam_ids[exam_dir.name] = ids

# ─── 4) 라우팅 정의 ───────────────────────────────────────
@app.route('/')
def index():
    """
    정적 파일(frontend/index.html)을 제공.
    이게 로그인 페이지 역할을 함.
    """
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

@app.route('/api/authenticate')
def api_authenticate():
    """
    로그인용 API.
    쿼리스트링으로 ?id=<리클래스ID>를 받음.
    student_list.csv에 ID가 있으면 {authenticated: true}, 아니면 401 반환.
    """
    rid = request.args.get('id', '').strip()
    if not rid:
        return jsonify({'error': 'Missing id parameter'}), 400

    ok = authenticate(rid)
    return jsonify({'authenticated': ok}), (200 if ok else 401)

@app.route('/api/exams')
def api_exams():
    """
    메인 페이지에서 회차(시험명) 목록을 가져갈 때 사용하는 API.
    data/ 디렉터리 바로 아래에 있는 모든 폴더 이름을 회차로 반환.
    """
    exams = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]
    return jsonify(exams)

@app.route('/api/check_exam')
def api_check_exam():
    """
    사용자가 선택한 시험 회차와 로그인 ID를 넘겨서, 실제 응시 정보가 있는지 확인.
    쿼리스트링: ?exam=<시험명>&id=<리클래스ID>
    """
    exam = request.args.get('exam', '').strip()
    rid  = request.args.get('id', '').strip()
    if not exam or not rid:
        return jsonify({'error': 'Missing parameters'}), 400

    if exam not in exam_ids:
        return jsonify({'error': 'Unknown exam'}), 404

    registered = rid in exam_ids[exam]
    return jsonify({
        'registered': registered,
        'error': None if registered else '해당 모의고사의 응시 정보가 없습니다.'
    }), (200 if registered else 404)

@app.route('/report_card/<exam>/<rid>')
def serve_report_card(exam: str, rid: str):
    """
    “성적표 확인” 기능을 위해, report card 폴더에서 해당 학생의 PNG를 찾아주는 예시 라우트.
    예를 들어:
      GET /report_card/Spurt 모의고사 08회/홍길동7860
    라고 요청하면,
      data/Spurt 모의고사 08회/report card/ 폴더 내에 “홍길동7860_*.png” 형태를 찾아서 리턴.
    실제 정적 제공이 필요하면 send_from_directory를 쓰면 됩니다.
    """
    exam_dir = DATA_DIR / exam / 'report card'
    if not exam_dir.is_dir():
        return jsonify({'error': 'Report card 폴더가 없습니다.'}), 404

    # 해당 리클래스 ID가 들어간 파일 검색
    matches = list(exam_dir.rglob(f"{rid}*.png"))
    if not matches:
        return jsonify({'error': 'Report card 파일을 찾을 수 없습니다.'}), 404

    # 첫 번째 결과를 리턴(여러 개라면 첫 번째만)
    file_path = matches[0]
    return send_from_directory(str(file_path.parent), file_path.name)

# ─── 5) 앱 실행 ─────────────────────────────────────────
if __name__ == '__main__':
    # Railway 등에서는 Start Command를 “waitress-serve --port $PORT app:app”으로 설정하므로
    # 아래 코드는 로컬 개발 환경에서만 Flask 내장 서버 실행용으로 남겨둡니다.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
