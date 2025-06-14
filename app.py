# app.py
import os
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# 1) 답안 키 로딩 (정답이 빈칸인 행 제거)
def load_answer_key(exam):
    path = os.path.join('data', exam, 'answer', 'A.csv')
    df = pd.read_csv(path, dtype=str)
    df = df[df['정답'].notna() & (df['정답'] != '')]
    return {int(r['문항번호']): r['정답'] for _, r in df.iterrows()}

# 2) 학생 답안 로딩 (빈칸은 제외)
def load_student_answers(exam, student_id):
    path = os.path.join('data', exam, 'student_answer', f'{student_id}.csv')
    df = pd.read_csv(path, dtype=str)
    row = df.iloc[0].to_dict()
    smap = {}
    for k, v in row.items():
        try:
            q = int(k)
        except ValueError:
            continue
        if v and v.strip() != '':
            smap[q] = v
    return smap

# 1) ID 인증
@app.route('/api/authenticate')
def authenticate():
    student_id = request.args.get('id')
    df = pd.read_csv(os.path.join('data', 'student_list.csv'), dtype=str)
    if student_id in df.iloc[:,0].tolist():
        return jsonify({'authenticated': True})
    return jsonify({'authenticated': False})

# 2) 시험 회차 목록 반환
@app.route('/api/exams')
def exams():
    exams = [d for d in os.listdir('data') if os.path.isdir(os.path.join('data', d)) and d!='student_list.csv']
    return jsonify(exams)

# 3) 응시 여부 확인
@app.route('/api/check_exam')
def check_exam():
    exam = request.args.get('exam')
    student_id = request.args.get('id')
    path = os.path.join('data', exam, 'student_answer', f'{student_id}.csv')
    return jsonify({'taken': os.path.exists(path)})

# 4) 성적표 이미지 반환
@app.route('/api/reportcard')
def reportcard():
    exam = request.args.get('exam')
    student_id = request.args.get('id')
    img_dir = os.path.join('data', exam, 'report card', student_id)
    if os.path.isdir(img_dir):
        files = os.listdir(img_dir)
        if files:
            return jsonify({'url': f'/report/{exam}/{student_id}/{files[0]}'})
    return jsonify({'error': '성적표 없음'})

@app.route('/report/<exam>/<student_id>/<filename>')
def serve_report(exam, student_id, filename):
    directory = os.path.join('data', exam, 'report card', student_id)
    return send_from_directory(directory, filename)

# 5) 틀린 문제 목록 반환
@app.route('/api/review')
def review():
    exam       = request.args.get('exam')
    student_id = request.args.get('id')
    answer_map  = load_answer_key(exam)
    student_map = load_student_answers(exam, student_id)

    wrong_list = []
    for qno, correct in answer_map.items():
        # answer_map에만 있고 student_map엔 없거나, 답이 다르면 오답
        if student_map.get(qno) != correct:
            wrong_list.append(qno)
    return jsonify({'wrongList': [{'question': q} for q in wrong_list]})

# 6) 개별 문제 이미지 반환 (문제 다시 풀기)
@app.route('/api/review_question')
def review_question():
    exam = request.args.get('exam')
    qno  = request.args.get('question')
    return send_from_directory(
        os.path.join('data', exam, 'problem_images'),
        f'{qno}.png'
    )

# 7) 채점 후 정답 여부 반환
@app.route('/api/submit_review')
def submit_review():
    exam       = request.args.get('exam')
    qno        = int(request.args.get('question'))
    student_ans= request.args.get('answer')
    answer_map = load_answer_key(exam)

    if qno not in answer_map:
        return jsonify({'error': 'No such question'}), 400
    is_correct = (student_ans == answer_map[qno])
    return jsonify({'correct': is_correct})

# 8) OX 퀴즈 선지 및 정답 반환
@app.route('/api/quiz_sentences')
def quiz_sentences():
    exam = request.args.get('exam')
    qno  = request.args.get('question')
    path = os.path.join('data', exam, 'ox', 'OX.csv')
    df = pd.read_csv(path, dtype=str)
    df = df[df['문항번호'] == str(qno)]
    sentences = []
    for _, r in df.iterrows():
        sentences.append({'text': r['선지'], 'correct': (r['O/X'] == 'O')})
    return jsonify({'sentences': sentences})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
