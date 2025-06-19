# app.py

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

# ── 0) 프론트엔드 서빙 ──
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if path and target.exists():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

# ── 디버그: 각 시험 폴더 내 student_answer 상태 확인 ──
@app.route('/api/debug_exams')
def debug_exams():
    result = {}
    for d in DATA_DIR.iterdir():
        if d.is_dir():
            student_dir = d / 'student_answer'
            exists = student_dir.is_dir()
            files  = list(student_dir.glob('*.csv')) if exists else []
            result[d.name] = {
                'student_answer_exists': exists,
                'csv_count': len(files),
                'csv_files': [f.name for f in files]
            }
    return jsonify(result)

# ── 인증용 ID 목록 로드 ──
STUDENT_LIST_CSV = DATA_DIR / 'student_list.csv'
valid_ids = set()
if STUDENT_LIST_CSV.exists():
    with open(STUDENT_LIST_CSV, encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                valid_ids.add(row[0].strip())

@app.route('/api/authenticate')
def api_authenticate():
    user_id = request.args.get('id','').strip()
    return jsonify(authenticated=(user_id in valid_ids))

# ── 시험 회차 목록: data/ 폴더 내 모든 디렉토리 ──
@app.route('/api/exams')
def api_get_exams():
    exams = [
        d.name for d in DATA_DIR.iterdir()
        if d.is_dir() and d.name != 'student_list.csv'
    ]
    return jsonify(sorted(exams))

# ── 응시 여부 확인 ──
@app.route('/api/check_exam')
def api_check_exam():
    user_id = request.args.get('id','').strip()
    exam    = request.args.get('exam','').strip()
    stud_dir = DATA_DIR / exam / 'student_answer'
    exists = stud_dir.is_dir() and any(stud_dir.glob('*.csv'))
    return jsonify(registered=exists, error=None if exists else '응시 정보가 없습니다.')

# ── 성적표 이미지 반환 ──
@app.route('/api/reportcard')
def api_reportcard():
    user_id = request.args.get('id','').strip()
    exam    = request.args.get('exam','').strip()
    report_dir = DATA_DIR / exam / 'report card'
    if not report_dir.is_dir():
        return jsonify(error='report card 폴더가 없습니다.'), 404
    for img in report_dir.rglob(f'*{user_id}*.png'):
        rel = img.relative_to(report_dir)
        return jsonify(url=f'/report/{exam}/{rel.as_posix()}')
    return jsonify(error='성적표를 찾을 수 없습니다.'), 404

@app.route('/report/<exam>/<path:subpath>')
def serve_report(exam, subpath):
    report_dir = DATA_DIR / exam / 'report card'
    return send_from_directory(str(report_dir), subpath)

# ── 틀린 문제 목록 반환 (1–16번 빈칸 스킵) ──
@app.route('/api/review')
def api_review():
    exam    = request.args.get('exam','').strip()
    user_id = request.args.get('id','').strip()

    ans_path = DATA_DIR / exam / 'answer' / 'A.csv'
    if not ans_path.exists():
        return jsonify(error='정답 파일이 없습니다.'), 404
    raw = pd.read_csv(ans_path, header=None, dtype=str)
    ans_list = raw.iloc[1:, 2].astype(str).tolist()

    # 학생 답안 로드
    student_answers = None
    stud_dir = DATA_DIR / exam / 'student_answer'
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
    if student_answers is None:
        return jsonify(error='응시 정보가 없습니다.'), 404

    # 오답 목록 생성: 둘 다 빈칸인 경우만 스킵
    wrong_list = []
    for i, correct in enumerate(ans_list):
        c = correct.strip()
        s = str(student_answers[i]).strip() if i < len(student_answers) else ''
        if c == '' and s == '':
            continue
        if s != c:
            wrong_list.append({'question': i+1})
    return jsonify(wrongList=wrong_list)

# ── 개별 틀린 문제 이미지 서빙 ──
@app.route('/api/review_question')
def api_review_question():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','').strip())
    return jsonify(
        image_url=f'/problem_images/{exam}/{question}.png',
        choices=[1,2,3,4,5]
    )

# ── 채점 후 정답 여부 반환 ──
@app.route('/api/submit_review')
def api_submit_review():
    exam     = request.args.get('exam','').strip()
    question = int(request.args.get('question','').strip())
    answer   = request.args.get('answer','').strip()
    raw      = pd.read_csv(DATA_DIR / exam / 'answer' / 'A.csv', header=None, dtype=str)
    correct  = raw.iat[question, 2].strip()
    return jsonify(correct=(answer == correct))

# ── OX 퀴즈 선지 및 정답 반환 ──
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
                sentences.append({'text': row[1].strip(), 'correct': row[2].strip().upper() == 'O'})
    if not sentences:
        return jsonify(error='해당 문장의 정의가 없습니다.'), 404
    return jsonify(sentences=sentences)

# ── 이미지 서빙 ──
@app.route('/problem_images/<exam>/<path:filename>')
def serve_problem_image(exam, filename):
    img_dir = DATA_DIR / exam / 'problem_images'
    return send_from_directory(str(img_dir), filename)

@app.route('/exp_images/<exam>/<path:filename>')
def serve_exp_images(exam, filename):
    img_dir = DATA_DIR / exam / 'exp_images'
    return send_from_directory(str(img_dir), filename)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=True
    )
