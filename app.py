# app.py
# app.py 맨 위 import 직후에 추가
from flask import current_app as app

# 디버그: data/ 하위 폴더 + student_answer/*.csv 현황 반환
@app.route('/api/debug_exams')
def debug_exams():
    result = {}
    for d in (DATA_DIR).iterdir():
        if d.is_dir():
            student_dir = d / 'student_answer'
            result[d.name] = {
                'student_answer_exists': student_dir.is_dir(),
                'csv_count': len(list(student_dir.glob('*.csv'))) if student_dir.exists() else 0,
                'csv_files': [f.name for f in student_dir.glob('*.csv')] if student_dir.exists() else []
            }
    return jsonify(result)

import os
import csv
import pandas as pd
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR     = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR     = BASE_DIR / "data"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

# ── 1) 인증용 ID 목록 로드 ──
STUDENT_LIST_CSV = DATA_DIR / 'student_list.csv'
valid_ids = set()
if STUDENT_LIST_CSV.exists():
    with open(STUDENT_LIST_CSV, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                valid_ids.add(row[0].strip())

# ── 2) 회차별 응시자 ID 집합 생성 ──
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

# ── API 엔드포인트 ──

# 루트 경로에 프론트엔드 서빙
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if path and target.exists():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

@app.route('/api/authenticate')
def api_authenticate():
    user_id = request.args.get('id','').strip()
    return jsonify(authenticated=(user_id in valid_ids))

@app.route('/api/exams')
def api_get_exams():
    return jsonify(sorted(exam_ids.keys()))

@app.route('/api/check_exam')
def api_check_exam():
    user_id = request.args.get('id','').strip()
    exam    = request.args.get('exam','').strip()
    if exam not in exam_ids:
        return jsonify(registered=False, error='존재하지 않는 회차입니다.')
    return jsonify(
        registered=(user_id in exam_ids[exam]),
        error=None if user_id in exam_ids[exam] else '응시 정보가 없습니다.'
    )

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

@app.route('/api/review')
def api_review():
    exam    = request.args.get('exam','').strip()
    user_id = request.args.get('id','').strip()

    # 1) 정답 CSV 로드
    ans_path = DATA_DIR / exam / 'answer' / 'A.csv'
    if not ans_path.exists():
        return jsonify(error='정답 파일이 없습니다.'), 404
    raw = pd.read_csv(ans_path, header=None, dtype=str)
    # raw.iloc[1:,2] 에 정답이 들어있다고 가정
    ans_list = raw.iloc[1:, 2].astype(str).tolist()

    # 2) 학생 답안 찾기
    stud_dir = DATA_DIR / exam / 'student_answer'
    student_answers = None
    if stud_dir.is_dir():
        for csv_file in stud_dir.glob('*.csv'):
            df = pd.read_csv(csv_file, header=None, dtype=str)
            for row in df.itertuples(index=False):
                sid = str(row[0]).strip() + str(row[1]).strip()[-4:]
                if sid == user_id:
                    student_answers = list(row)[2:2+len(ans_list)]
                    break
            if student_answers is not None:
                break

    if not student_answers:
        return jsonify(error='응시 정보가 없습니다.'), 404

    # 3) 오답 목록 생성 (정답·답안 모두 빈칸인 경우만 제외)
    wrong_list = []
    for i, stud in enumerate(student_answers):
        correct = ans_list[i].strip()
        s       = str(stud).strip()
        # 정답 키도 빈칸이고, 학생 답안도 빈칸이면 건너뛰기
        if correct == '' and s == '':
            continue
        # 그렇지 않고 답이 다르면 오답
        if s != correct:
            wrong_list.append({'question': i+1})
    return jsonify(wrongList=wrong_list)

@app.route('/api/review_question')
def api_review_question():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','0'))
    return jsonify(
        image_url=f'/problem_images/{exam}/{question}.png',
        choices=[1,2,3,4,5]
    )

@app.route('/api/submit_review')
def api_submit_review():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','').strip())
    answer   = request.args.get('answer','').strip()
    raw      = pd.read_csv(DATA_DIR / exam / 'answer' / 'A.csv', header=None, dtype=str)
    correct  = raw.iat[question, 2].strip()
    return jsonify(correct=(answer == correct))

@app.route('/api/quiz_sentences')
def api_quiz_sentences():
    exam     = request.args.get('exam','').strip()
    question = request.args.get('question','').strip()
    csv_path = DATA_DIR / exam / 'OX' / 'OX.csv'
    if not csv_path.exists():
        return jsonify(error='OX.csv 파일이 없습니다.'), 404
    sentences = []
    current_q = None
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3:
                continue
            first = str(row[0]).strip()
            if first:
                current_q = first
            if current_q == question:
                sentences.append({
                    'text':    row[1].strip(),
                    'correct': row[2].strip().upper() == 'O'
                })
    if not sentences:
        return jsonify(error='해당 문장의 정의가 없습니다.'), 404
    return jsonify(sentences=sentences)

@app.route('/problem_images/<exam>/<path:filename>')
def serve_problem_image(exam, filename):
    img_dir = DATA_DIR / exam / 'problem_images'
    return send_from_directory(str(img_dir), filename)

@app.route('/exp_images/<exam>/<path:filename>')
def serve_exp_images(exam, filename):
    img_dir = DATA_DIR / exam / 'exp_images'
    return send_from_directory(str(img_dir), filename)

@app.route('/report/<exam>/<path:subpath>')
def serve_report(exam, subpath):
    report_dir = DATA_DIR / exam / 'report card'
    return send_from_directory(str(report_dir), subpath)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT',5000)),
        debug=True
    )
