
ffrom flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import os

# 🔧 HTML 경로 절대경로로 지정
app = Flask(__name__, static_folder=os.path.join(os.getcwd(), "frontend"), static_url_path="")

STUDENT_CSV = "backend/data/S.CSV"
ANSWER_CSV = "backend/data/A.CSV"

try:
    students_df = pd.read_csv(STUDENT_CSV)
    answers_raw = pd.read_csv(ANSWER_CSV, header=None)
    answers_df = answers_raw.iloc[1:].copy()
    answers_df.columns = ["회차", "문제번호", "정답", "배점", "문제유형"]
    correct_answers = answers_df["정답"].astype(int).tolist()
except Exception as e:
    print("CSV 로딩 실패:", e)
    students_df = pd.DataFrame()
    correct_answers = []

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/check_id", methods=["POST"])
def check_id():
    data = request.get_json()
    student_id = data.get("id")

    for _, row in students_df.iterrows():
        name = row["성명"]
        phone = str(row["전화번호"]).split("-")[-1]
        expected_id = name + phone

        if expected_id == student_id:
            answers = row[list(map(str, range(1, 21)))].tolist()
            wrongs = [
                i + 1 for i, a in enumerate(answers)
                if str(a).strip() and int(a) != correct_answers[i]
            ]
            return jsonify({"status": "success", "wrongs": wrongs})

    return jsonify({"status": "error", "message": "학생 ID가 없습니다."})

# ✅ Render 포트 바인딩용 waitress 실행
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)

