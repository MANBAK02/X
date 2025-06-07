import os
import csv
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort

# 기본 경로 설정
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

# 1) student_list.csv 로부터 인증 가능한 ID 집합 생성
STUDENT_CSV = DATA_DIR / "student_list.csv"
student_ids = set()
with open(STUDENT_CSV, encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader, None)  # 헤더 스킵
    for row in reader:
        raw_id = row[0].lstrip('\ufeff').strip()
        student_ids.add(raw_id)

# 2) Flask 앱 초기화 (프론트엔드 정적 파일 제공 설정)
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

# 3) SPA 라우팅: 프론트엔드 파일이 있으면 서빙, 없으면 index.html
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if target.exists() and target.is_file():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

# 4) 인증 엔드포인트
@app.route('/api/authenticate')
def authenticate():
    user_id = request.args.get('id', '').strip()
    if user_id in student_ids:
        return jsonify({ 'authenticated': True })
    return jsonify({ 'authenticated': False, 'error': '인증되지 않은 ID입니다.' })

# 5) 회차 목록 제공 엔드포인트
@app.route('/api/exams')
def list_exams():
    try:
        exams = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]
        return jsonify({ 'exams': exams })
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500

# 6) 응시 여부 확인 엔드포인트
@app.route('/api/check_exam')
def check_exam():
    exam = request.args.get('exam', '').strip()
    user_id = request.args.get('id', '').strip()
    student_dir = DATA_DIR / exam / 'student_answer'
    if not student_dir.exists():
        return jsonify({ 'registered': False, 'error': '응시 정보가 없습니다.' })
    for csv_file in student_dir.glob('*.csv'):
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('이름', '').strip()
                phone = row.get('전화번호', '').strip()
                digits = ''.join(filter(str.isdigit, phone))
                identifier = name + digits[-8:]
                if identifier == user_id:
                    return jsonify({ 'registered': True })
    return jsonify({ 'registered': False, 'error': '응시 정보가 없습니다.' })

# 7) 성적표 이미지 URL 제공 엔드포인트
@app.route('/api/reportcard')
def reportcard():
    exam = request.args.get('exam', '').strip()
    user_id = request.args.get('id', '').strip()
    report_dir = DATA_DIR / exam / 'report_card'
    if not report_dir.exists():
        return jsonify({ 'error': '성적표를 찾을 수 없습니다.' }), 404
    for img in report_dir.rglob('*.png'):
        if user_id in img.name:
            return jsonify({ 'url': f"/api/reportcard/image?path={img.as_posix()}" })
    return jsonify({ 'error': '성적표를 찾을 수 없습니다.' }), 404

# 8) 성적표 이미지 서빙 엔드포인트
@app.route('/api/reportcard/image')
def reportcard_image():
    path = request.args.get('path', '')
    img = Path(path)
    if img.exists():
        return send_from_directory(str(img.parent), img.name)
    abort(404)

# 9) 틀린 문제 다시 풀기 & OX 퀴즈 플레이스홀더
@app.route('/api/review')
def review():
    return jsonify({ 'error': '미구현 기능입니다.' }), 501

@app.route('/api/quiz')
def quiz():
    return jsonify({ 'error': '미구현 기능입니다.' }), 501

# 10) 앱 실행
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
