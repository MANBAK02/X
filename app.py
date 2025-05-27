import os
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'S.CSV')
STATIC_FOLDER = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')

try:
    df = pd.read_csv(DATA_PATH)
    print("CSV 로딩 성공:", DATA_PATH)
except Exception as e:
    print("CSV 로딩 실패:", e)
    df = pd.DataFrame()

@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/api/score')
def get_score():
    name = request.args.get('id')
    if not name or df.empty:
        return jsonify({'error': 'Invalid request or empty data'}), 400

    result = df[df['name'] == name]
    if result.empty:
        return jsonify({'error': 'Student not found'}), 404

    return jsonify(result.to_dict(orient='records'))

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port)
