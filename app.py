# app.py
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
import pandas as pd

app = Flask(
    __name__,
    static_folder='frontend',   # 정적 파일(HTML/CSS/JS)이 들어있는 폴더
    static_url_path='/'         # 루트 경로에서 static_folder를 찾아 서빙
)

# ┌───────────────────────────────────────────────────
# │ 1) 인증용 ID 집합 로드: data/student_list.csv
# └───────────────────────────────────────────────────
DATA_DIR = Path('data')
STUDENT_LIST_CSV = DATA_DIR / 'student_list.csv'

valid_ids = set()
if STUDENT_LIST_CSV.exists():
    # header=None으로 읽어서 첫 번째 열 전체를 ID로 간주
    df_student_list = pd.read_csv(STUDENT_LIST_CSV, header=None, dtype=str)
    for val in df_student_list.iloc[:, 0].dropna().astype(str):
        valid_ids.add(val.strip())
    print(f"[DEBUG] 인증 가능한 ID 총 {len(valid_ids)}개 로드됨.")
else:
    print("[WARN] data/student_list.csv 파일이 존재하지 않습니다.")

# ┌───────────────────────────────────────────────────
# │ 2) 시험별 “응시자 ID 집합” 생성
# │   - 데이터 디렉터리 구조 (예시)
# │     data/
# │       └─ <시험명1>/
# │             ├─ student_answer/   <-- 학생별 답안 CSV들 (첫 열=이름, 둘째 열=전화번호(8자리, 010 제외))
# │             ├─ report card/      <-- 성적표 PNG 파일들
# │             └─ (기타 폴더들)
# │       └─ <시험명2>/ …
# └───────────────────────────────────────────────────
exam_ids = {}  # { '시험명1': {'홍길동1234', …}, '시험명2': {…}, … }

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    student_ans_dir = exam_dir / 'student_answer'
    ids_for_this_exam = set()

    if student_ans_dir.is_dir():
        for csv_path in student_ans_dir.glob('*.csv'):
            try:
                df_ans = pd.read_csv(csv_path, dtype=str, header=None)
            except Exception as e:
                print(f"[WARN] {csv_path} 읽는 중 오류: {e}")
                continue

            # 첫 열: 이름, 둘째 열: 전화번호(8자리라고 가정)
            for row in df_ans.itertuples(index=False):
                name = str(row[0]).strip() if len(row) >= 1 else ''
                phone8 = str(row[1]).strip() if len(row) >= 2 else ''
                if len(phone8) >= 4:
                    reclass_id = name + phone8[-4:]
                    ids_for_this_exam.add(reclass_id)
    if ids_for_this_exam:
        exam_ids[exam_dir.name] = ids_for_this_exam
        print(f"[DEBUG] Exam '{exam_dir.name}' → 응시자 리클래스 ID: {sorted(ids_for_this_exam)}")
    else:
        print(f"[DEBUG] Exam '{exam_dir.name}' → student_answer 폴더가 없거나, ID 생성 불가")

# ┌───────────────────────────────────────────────────
# │ 3) Flask API 엔드포인트 정의
# └───────────────────────────────────────────────────

@app.route('/api/authenticate')
def api_authenticate():
    """
    로그인 시 호출: ?id=<리클래스ID>
    → data/student_list.csv 첫 번째 열에서만 비교
    """
    user_id = request.args.get('id', '').strip()
    if user_id in valid_ids:
        return jsonify(authenticated=True)
    else:
        return jsonify(authenticated=False)


@app.route('/api/exams')
def api_get_exams():
    """
    로그인 후 호출: 시험(회차) 목록을 JSON array로 반환
    """
    return jsonify(sorted(exam_ids.keys()))


@app.route('/api/check_exam')
def api_check_exam():
    """
    회차 선택 후 호출: ?exam=<시험명>&id=<리클래스ID>
    → exam_ids[시험명] 집합에 ID가 있는지 확인
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
    “내 성적표 확인” 버튼 클릭 시 호출: ?exam=<시험명>&id=<리클래스ID>
    → data/<시험명>/report card/ 하위에서 <ID>가 포함된 .png 파일명을 찾아
       JSON { "url": "/report/<시험명>/<파일명>.png" }으로 반환
    """
    user_id = request.args.get('id', '').strip()
    exam = request.args.get('exam', '').strip()

    exam_dir = DATA_DIR / exam
    if not exam_dir.is_dir():
        return jsonify(error='존재하지 않는 시험 회차입니다.')

    report_dir = exam_dir / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.')

    # report card/ 이하를 재귀 탐색하며 <ID>가 포함된 .png 파일 찾기
    for img_path in report_dir.rglob(f'*{user_id}*.png'):
        filename = img_path.name
        # 클라이언트가 "/report/<exam>/<filename>"으로 요청하면 send_report가 서빙함
        url = f'/report/{exam}/{filename}'
        return jsonify(url=url)

    return jsonify(error='성적표를 찾을 수 없습니다.')


@app.route('/report/<exam>/<filename>')
def send_report(exam, filename):
    """
    실제 이미지 파일을 서빙하는 엔드포인트
    - 클라이언트는 "/report/<exam>/<filename>"으로 GET 요청
    - 이 함수가 data/<exam>/report card/<filename> 파일을 보내줌
    """
    report_folder = DATA_DIR / exam / 'report card'
    return send_from_directory(report_folder, filename)


# ┌───────────────────────────────────────────────────
# │ 4) SPA 스타일 정적 파일 서빙 (React/Vue 없이 간단하게 index.html 리턴)
# └───────────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    1) 요청이 실제 static (CSS/JS/이미지 등) 파일이면 그대로 서빙
    2) 그 외 모든 요청은 frontend/index.html 반환 →  
       (Single Page Application 방식 흉내)
    """
    static_dir = Path(app.static_folder)  # 'frontend' 디렉터리
    requested = static_dir / path

    if path != "" and requested.exists():
        # 예: /favicon.ico, /main.js, /globe.gif 등 실제 파일 서빙
        return send_from_directory(app.static_folder, path)
    else:
        # 나머지는 모두 index.html 로 리턴
        return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    # 로컬 개발 시: Flask 내장 서버로 실행 (배포 시에는 waitress/gunicorn 사용 권장)
    app.run(host='0.0.0.0', port=5000, debug=True)
