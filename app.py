# app.py
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
import pandas as pd

app = Flask(
    __name__,
    static_folder='frontend',     # 정적 파일(HTML/JS/CSS)이 있는 폴더
    static_url_path='/'           # 루트( / )로 접근 시 frontend/index.html 을 띄우게 함
)

# ┌───────────────────────────────────────────────────────────────
# │ 1) student_list.csv 로부터 “인증용 ID(리클래스 ID)” 집합을 미리 생성
# └───────────────────────────────────────────────────────────────
STUDENT_CSV_PATH = Path('data') / 'student_list.csv'
valid_ids = set()

if STUDENT_CSV_PATH.exists():
    df_students = pd.read_csv(STUDENT_CSV_PATH, dtype=str)  # header 포함해서 읽음
    # 컬럼명이 “이름”과 “전화번호”로 되어 있어야 한다고 가정
    if '이름' in df_students.columns and '전화번호' in df_students.columns:
        for _, row in df_students.iterrows():
            name = str(row['이름']).strip()
            phone8 = str(row['전화번호']).strip()  # “010” 뺀 8자리
            if len(phone8) >= 4:
                reclass_id = name + phone8[-4:]
                valid_ids.add(reclass_id)
    else:
        # 만약 “리클래스ID” 라는 별도 컬럼이 이미 존재한다면…
        if '리클래스ID' in df_students.columns:
            valid_ids = set(df_students['리클래스ID']
                            .dropna().astype(str).str.strip())

    print(f"[DEBUG] 인증 가능한 ID 총 {len(valid_ids)}개 로드됨.")


# ┌───────────────────────────────────────────────────────────────
# │ 2) data/ 폴더 밑에 있는 각 시험(예: Spurt 모의고사 07회 등) 디렉터리를 읽어서
# │    해당 시험에 응시한 리클래스 ID 집합을 미리 생성
# └───────────────────────────────────────────────────────────────
DATA_DIR = Path('data')
exam_ids = {}   # { 'Spurt 모의고사 07회': { '홍길동5678', '김민수1234', … }, … }

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    ids = set()
    ans_dir = exam_dir / 'student_answer'
    if ans_dir.is_dir():
        # student_answer 폴더 안의 모든 .csv 파일을 읽어서 ID를 조합
        for csv_path in ans_dir.glob('*.csv'):
            try:
                df = pd.read_csv(csv_path, dtype=str)  # 첫 줄을 헤더로 인식
            except Exception as e:
                print(f"[WARN] {csv_path} 를 읽는 중 오류: {e}")
                continue

            # “1열: 이름” + “2열: 전화번호(8자리, 010 제외)” 로 ID 조합
            if '이름' in df.columns and '전화번호' in df.columns:
                for _, row in df.iterrows():
                    name = str(row['이름']).strip()
                    phone8 = str(row['전화번호']).strip()
                    if len(phone8) >= 4:
                        reclass = name + phone8[-4:]
                        ids.add(reclass)
            else:
                # 헤더가 없거나 컬럼명이 다를 때, 첫 번째 열이 이름, 두 번째 열이 전화번호라는 가정
                for _, row in df.iterrows():
                    name = str(row.iloc[0]).strip()
                    phone8 = str(row.iloc[1]).strip() if len(row) > 1 else ''
                    if len(phone8) >= 4:
                        reclass = name + phone8[-4:]
                        ids.add(reclass)

    if ids:
        exam_ids[exam_dir.name] = ids
        print(f"[DEBUG] Exam '{exam_dir.name}' → 응시자 리클래스 ID: {sorted(ids)}")
    else:
        print(f"[DEBUG] Exam '{exam_dir.name}' → student_answer 폴더에 CSV가 없거나, ID를 못 구함")


# ┌───────────────────────────────────────────────────────────────
# │ 3) Flask 엔드포인트
# └───────────────────────────────────────────────────────────────

@app.route('/api/authenticate')
def api_authenticate():
    """
    로그인 페이지에서 넘어오는 ?id=xxx 에 대해, valid_ids 에 포함되어 있으면 authenticated=True 리턴
    """
    user_id = request.args.get('id', '').strip()
    if user_id in valid_ids:
        return jsonify(authenticated=True)
    else:
        return jsonify(authenticated=False)


@app.route('/api/exams')
def api_get_exams():
    """
    로그인 후, 회차 선택(select box)에 들어갈 시험(폴더) 목록을 보냄.
    """
    return jsonify(sorted(exam_ids.keys()))


@app.route('/api/check_exam')
def api_check_exam():
    """
    회차 선택 후 “해당 회차에 해당 ID가 있나?” 를 확인.
    /api/check_exam?exam=Spurt 모의고사 07회&id=홍길동5678
    """
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
    """
    “내 성적표 확인” 버튼 클릭 시 호출.
    /api/reportcard?exam=Spurt 모의고사 07회&id=홍길동5678
    → data/Spurt 모의고사 07회/report card/ 폴더 아래에서
      파일 이름에 “홍길동5678”이 포함된 .png 파일을 재귀 탐색하여 URL로 반환
    """
    user_id = request.args.get('id', '').strip()
    exam = request.args.get('exam', '').strip()

    # 1) 우선 exam 폴더가 존재하는지 확인
    exam_dir = DATA_DIR / exam
    if not exam_dir.is_dir():
        return jsonify(error='존재하지 않는 시험 회차입니다.')

    # 2) report card 폴더가 있는지 확인
    report_dir = exam_dir / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.')

    # 3) report card 디렉터리 및 하위 폴더를 재귀적으로 뒤져서
    #    “파일명에 user_id 가 포함된 .png”를 찾는다.
    for img_path in report_dir.rglob(f'*{user_id}*.png'):
        # 클라이언트가 접근할 수 있는 정적 URL 경로를 만들어서 돌려줌
        rel_path = img_path.relative_to(Path.cwd())
        url = '/' + str(rel_path).replace(os.path.sep, '/')
        return jsonify(url=url)

    # 못 찾으면 오류 메시지
    return jsonify(error='성적표를 찾을 수 없습니다.')


# ┌───────────────────────────────────────────────────────────────
# │ 4) 그 외 모든 경로( '/', '/어떤파일.js' 등)는 frontend/index.html (SPA)로 서빙
# └───────────────────────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # app.static_folder 는 문자열이므로, Path로 변환해서 써야 합니다.
    static_dir = Path(app.static_folder)

    requested = static_dir / path
    if path != "" and requested.exists():
        # 예: /favicon.ico 같은 정적 리소스가 있으면 바로 서빙
        return send_from_directory(app.static_folder, path)
    else:
        # 그 외에는 항상 index.html (SPA) 리턴
        return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    # production 환경에서는 flask가 아니라 gunicorn 등을 쓰게 될 테니, 
    # 개발 중일 때만 app.run을 띄우는 용도
    app.run(host='0.0.0.0', port=5000, debug=True)
