import os
import csv
import pandas as pd
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort

BASE_DIR     = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR     = BASE_DIR / "data"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

# 1) 로그인용 ID 목록 로드
STUDENT_LIST_CSV = DATA_DIR / 'student_list.csv'
valid_ids = set()
if STUDENT_LIST_CSV.exists():
    with open(STUDENT_LIST_CSV, encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row:
                valid_ids.add(row[0].strip())

# 2) 회차별 응시자 ID 집합 생성
exam_ids = {}
for exam_dir in DATA_DIR.iterdir():
    if not exam_dir.is_dir():
        continue
    ans_dir = exam_dir / 'student_answer'
    ids = set()
    if ans_dir.is_dir():
        for csv_path in ans_dir.glob('*.csv'):
            df = pd.read_csv(csv_path, header=None, dtype=str)
            for row in df.itertuples(index=False):
                sid = str(row[0]).strip() + str(row[1]).strip()[-4:]
                ids.add(sid)
    if ids:
        exam_ids[exam_dir.name] = ids

# 인증
@app.route('/api/authenticate')
def api_authenticate():
    user_id = request.args.get('id','').strip()
    return jsonify(authenticated=(user_id in valid_ids))

# 회차 목록
@app.route('/api/exams')
def api_get_exams():
    return jsonify(sorted(exam_ids.keys()))

# 응시 여부 확인
@app.route('/api/check_exam')
def api_check_exam():
    user_id = request.args.get('id','').strip()
    exam    = request.args.get('exam','').strip()
    if exam not in exam_ids:
        return jsonify(registered=False, error='존재하지 않는 회차입니다.')
    return jsonify(registered=(user_id in exam_ids[exam]),
                   error=None if user_id in exam_ids[exam] else '응시 정보가 없습니다.')

# 성적표 조회
@app.route('/api/reportcard')
def api_reportcard():
    user_id    = request.args.get('id','').strip()
    exam       = request.args.get('exam','').strip()
    report_dir = DATA_DIR / exam / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.')
    for img in report_dir.rglob(f'*{user_id}*.png'):
        rel = img.relative_to(report_dir)
        return jsonify(url=f'/report/{exam}/{rel.as_posix()}')
    return jsonify(error='성적표를 찾을 수 없습니다.')

# 틀린 문제 리스트 조회
@app.route('/api/review')
def api_review():
    exam    = request.args.get('exam','').strip()
    user_id = request.args.get('id','').strip()

    ans_path = DATA_DIR / exam / 'answer' / 'A.csv'
    if not ans_path.exists():
        return jsonify(error='정답 파일이 없습니다.'), 404
    raw      = pd.read_csv(ans_path, header=None, dtype=str)
    ans_list = raw.iloc[1:, 2].tolist()  # 정답은 세 번째 열

    stud_dir = DATA_DIR / exam / 'student_answer'
    student_answers = None
    for csv_file in stud_dir.glob('*.csv'):
        df = pd.read_csv(csv_file, header=None, dtype=str)
        for row in df.itertuples(index=False):
            sid = str(row[0]).strip() + str(row[1]).strip()[-4:]
            if sid == user_id:
                student_answers = list(row)[2:2+len(ans_list)]
                break
        if student_answers:
            break

    if not student_answers:
        return jsonify(error='응시 정보가 없습니다.'), 404

    wrong_list = []
    for i, stud in enumerate(student_answers):
        correct = ans_list[i].strip()
        s       = str(stud).strip()
        if not s.isdigit() or s != correct:
            wrong_list.append({'question': i+1})
    return jsonify(wrongList=wrong_list)

# 개별 문제 조회
@app.route('/api/review_question')
def api_review_question():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','0'))
    return jsonify(
        image_url=f'/problem_images/{exam}/{question}.png',
        choices=[1,2,3,4,5]
    )

# 정답 제출
@app.route('/api/submit_review')
def api_submit_review():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','').strip())
    answer   = request.args.get('answer','').strip()

    ans_path = DATA_DIR / exam / 'answer' / 'A.csv'
    raw      = pd.read_csv(ans_path, header=None, dtype=str)
    correct  = raw.iat[question, 2].strip()
    return jsonify(correct=(answer == correct))

# ── 디버그: problem_images 폴더 파일 목록 ──
@app.route('/api/debug/problem_images_files')
def api_debug_problem_images_files():
    exam = request.args.get('exam','').strip()
    d    = DATA_DIR / exam / 'problem_images'
    if not d.is_dir():
        return jsonify(error='problem_images 폴더가 없습니다.'), 404
    files = [p.name for p in d.iterdir() if p.is_file()]
    return jsonify(files=sorted(files))

# 문제 이미지 서빙
@app.route('/problem_images/<exam>/<path:filename>')
def serve_problem_image(exam, filename):
    img_dir = DATA_DIR / exam / 'problem_images'
    return send_from_directory(str(img_dir), filename)

# 해설 이미지 서빙
@app.route('/exp_images/<exam>/<path:filename>')
def serve_exp_images(exam, filename):
    img_dir = DATA_DIR / exam / 'exp_images'
    return send_from_directory(str(img_dir), filename)

# 성적표 이미지 서빙
@app.route('/report/<exam>/<path:subpath>')
def serve_report(exam, subpath):
    report_dir = DATA_DIR / exam / 'report card'
    return send_from_directory(str(report_dir), subpath)

# SPA 정적 파일 서빙
@app.route('/', defaults={'path':''})
@app.route('/<path:path>')
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if path and target.exists():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=True)
