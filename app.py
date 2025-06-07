```python
import os
import csv
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort

# Base directories
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

# Load student IDs\STUDENT_CSV = DATA_DIR / "student_list.csv"
student_ids = set()
with open(STUDENT_CSV, encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader, None)  # 헤더 스킵
    for row in reader:
        raw_id = row[0].lstrip("\ufeff").strip()
        student_ids.add(raw_id)

# Initialize Flask app
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

# Serve SPA
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if target.exists() and target.is_file():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

# Authentication endpoint
@app.route('/api/authenticate')
def authenticate():
    user_id = request.args.get('id', '').strip()
    if user_id in student_ids:
        return jsonify({'authenticated': True})
    return jsonify({'authenticated': False, 'error': '인증되지 않은 ID입니다.'})

# Exams list endpoint
@app.route('/api/exams')
def list_exams():
    try:
        exams = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]
        return jsonify({'exams': exams})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Check exam registration
@app.route('/api/check_exam')
def check_exam():
    exam = request.args.get('exam', '').strip()
    user_id = request.args.get('id', '').strip()
    student_dir = DATA_DIR / exam / 'student_answer'
    if not student_dir.exists():
        return jsonify({'registered': False, 'error': '응시 정보가 없습니다.'})
    for csv_file in student_dir.glob('*.csv'):
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('이름', '').strip()
                phone = row.get('전화번호', '').strip()
                digits = ''.join(filter(str.isdigit, phone))
                identifier = name + digits[-8:]
                if identifier == user_id:
                    return jsonify({'registered': True})
    return jsonify({'registered': False, 'error': '응시 정보가 없습니다.'})

# Report card endpoint
@app.route('/api/reportcard')
def reportcard():
    exam = request.args.get('exam', '').strip()
    user_id = request.args.get('id', '').strip()
    report_dir = DATA_DIR / exam / 'report_card'
    if not report_dir.exists():
        return jsonify({'error': '성적표를 찾을 수 없습니다.'}), 404
    for img in report_dir.rglob('*.png'):
        if user_id in img.name:
            return jsonify({'url': f"/api/reportcard/image?path={img.as_posix()}"})
    return jsonify({'error': '성적표를 찾을 수 없습니다.'}), 404

# Serve report card image
@app.route('/api/reportcard/image')
def reportcard_image():
    path = request.args.get('path', '')
    img = Path(path)
    if img.exists():
        return send_from_directory(str(img.parent), img.name)
    abort(404)

# Placeholders for review & quiz
@app.route('/api/review')
def review():
    return jsonify({'error': '미구현 기능입니다.'}), 501

@app.route('/api/quiz')
def quiz():
    return jsonify({'error': '미구현 기능입니다.'}), 501

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```
