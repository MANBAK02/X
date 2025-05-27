import os
from flask import Flask, request, jsonify, render_template
import pandas as pd

# 현재 파일 위치 기준 절대경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'S.CSV')
STATIC_FOLDER = os.path.join(BASE_DIR, 'frontend')

# Flask 앱 설정
app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')

# CSV 데이터 불러오기
try:
    df = pd.read_csv(DATA_PATH)
    print("CSV 로딩 성공:", DATA_PATH)
except Exception as e:
    print("CSV 로딩 실패:", e)
    df = pd.DataFrame()

# 메인 페이지
@app.route('/')
def index():
    index_path = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index_path):
        return app.send_static_file('index.html')
    else:
        return "index.html not found", 500

# API 예시 (학생 점수 반환)
@app.route('/api/score', methods=['GET'])
def get_score():
    student = request.args.get('name')
    if student and not df.empty:
        result = df[df['name'] == student]
        if not result.empty:
            return jsonify(result.to_dict(orient='records'))
        else:
            return jsonify({'error': 'Student not found'}), 404
    return jsonify({'error': 'Invalid request'}), 400

# 헬스 체크
@app.route('/health')
def health():
    return 'ok', 200

# 앱 실행 (개발용)
if __name__ == '__main__':
    app.run(debug=True)
