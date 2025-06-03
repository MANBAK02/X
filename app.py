# app.py
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
import pandas as pd

app = Flask(
    __name__,
    static_folder='frontend',     # 정적 파일이 위치한 폴더
    static_url_path='/'           # 루트( / ) 접근 시 index.html 서빙
)

# ┌──────────────────────────────────────────────────────
# │ 1) data/student_list.csv 에서 “인증용 ID” 집합만 로드
# └──────────────────────────────────────────────────────
# - student_list.csv 의 첫 번째 열(헤더 여부 상관없이)을 모두 ID로 간주
STUDENT_CSV = Path('data') / 'student_list.csv'
valid_ids = set()

if STUDENT_CSV.exists():
    # header=None 으로 읽어서 첫 번째 열 전체를 ID로 취급
    df_student_list = pd.read_csv(STUDENT_CSV, header=None, dtype=str)
    # 첫 번째 열의 모든 값(NaN 제외)을 strip 후 set에 추가
    for val in df_student_list.iloc[:, 0].dropna().astype(str):
        valid_ids.add(val.strip())
    print(f"[DEBUG] 인증 가능한 ID 총 {len(valid_ids)}개 로드됨.")
else:
    print("[WARN] data/student_list.csv 파일이 존재하지 않습니다.")

# ┌──────────────────────────────────────────────────────
# │ 2) data/ 폴더 바로 아래 각 시험(폴더)별로 “응시자 ID 집합” 생성
# └──────────────────────────────────────────────────────
# - 각 시험 폴더: data/<시험명>/
#     └─ student_answer/  ← 이 폴더 안의 CSV 파일들이 각각 학생 답안
#            첫 열: 이름, 둘째 열: 전화번호(8자리, “010” 제외)
#     └─ report card/     ← 이 폴더 이하에 성적표 PNG 이미지들
#
# 응시자 ID 집합은 (이름 + 전화번호 뒤 4자리) 조합으로 만듦
DATA_DIR = Path('data')
exam_ids = {}  # { '시험명1' : {'홍길동1234', ...}, '시험명2': {...}, ... }

for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue

    ids_for_this_exam = set()
    student_ans_dir = exam_dir / 'student_answer'
    if student_ans_dir.is_dir():
        # student_answer 폴더 안의 모든 .csv 파일을 읽는다
        for csv_path in student_ans_dir.glob('*.csv'):
            try:
                df_ans = pd.read_csv(csv_path, dtype=str, header=None)
            except Exception as e:
                print(f"[WARN] {csv_path} 읽는 중 오류: {e}")
                continue

            # 첫 번째 열: 이름, 두 번째 열: 전화번호(8자리라고 가정)
            for row in df_ans.itertuples(index=False):
                name = str(row[0]).strip() if len(row) >= 1 else ''
                phone8 = str(row[1]).strip() if len(row) >= 2 else ''
                # 전화번호가 8자리 이상이라면 뒤 4자리 추출
                if len(phone8) >= 4:
                    reclass_id = name + phone8[-4:]
                    ids_for_this_exam.add(reclass_id)
    # 응시자가 하나라도 있으면 등록
    if ids_for_this_exam:
        exam_ids[exam_dir.name] = ids_for_this_exam
        print(f"[DEBUG] Exam '{exam_dir.name}' → 응시자 리클래스 ID: {sorted(ids_for_this_exam)}")
    else:
        print(f"[DEBUG] Exam '{exam_dir.name}' → student_answer 폴더가 없거나, ID를 추출할 수 없음")


# ┌──────────────────────────────────────────────────────
# │ 3) Flask 엔드포인트 정의
# └──────────────────────────────────────────────────────

@app.route('/api/authenticate')
def api_authenticate():
    """
    로그인 시: ?id=<리클래스ID> 로 호출
    → data/student_list.csv 첫 번째 열에 ID가 있으면 authenticated=True
    """
    user_id = request.args.get('id', '').strip()
    if user_id in valid_ids:
        return jsonify(authenticated=True)
    else:
        return jsonify(authenticated=False)


@app.route('/api/exams')
def api_get_exams():
    """
    로그인 성공 후 호출: 회차 선택(select box)에 들어갈 시험(폴더) 목록 반환
    """
    return jsonify(sorted(exam_ids.keys()))


@app.route('/api/check_exam')
def api_check_exam():
    """
    회차 선택 후 호출: ?exam=<시험명>&id=<리클래스ID>
    → 해당 시험 student_answer CSV에서 이름+전화번호4자리로 조합한 ID 집합에
      전달된 ID가 있는지 확인
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
    → data/<시험명>/report card/ 이하를 재귀 탐색하며,
      파일명에 <리클래스ID>가 포함된 *.png 파일을 찾아 URL로 반환
    """
    user_id = request.args.get('id', '').strip()
    exam = request.args.get('exam', '').strip()

    exam_dir = DATA_DIR / exam
    if not exam_dir.is_dir():
        return jsonify(error='존재하지 않는 시험 회차입니다.')

    report_dir = exam_dir / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.')

    # 재귀적으로 report card/ 하위 모든 폴더에서 <user_id> 포함된 .png 찾기
    for img_path in report_dir.rglob(f'*{user_id}*.png'):
        rel = img_path.relative_to(Path.cwd())
        url = '/' + str(rel).replace(os.path.sep, '/')
        return jsonify(url=url)

    return jsonify(error='성적표를 찾을 수 없습니다.')


# ┌──────────────────────────────────────────────────────
# │ 4) 그 외 모든 경로( '/', '/어떤파일.js', '/favicon.ico' 등)는
# │    frontend/index.html 을 서빙 (SPA 방식)
# └──────────────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = Path(app.static_folder)

    requested = static_dir / path
    if path != "" and requested.exists():
        # 예: /favicon.ico, /main.js 등의 정적 파일 요청
        return send_from_directory(app.static_folder, path)
    else:
        # 나머지는 모두 index.html 반환
        return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    # 개발 모드: Flask 내장 서버 (배포 시에는 waitress/gunicorn 등으로 띄우세요)
    app.run(host='0.0.0.0', port=5000, debug=True)
