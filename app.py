import os
import csv
from pathlib import Path
from flask import Flask, request, jsonify, send\_from\_directory, abort

# 기본 경로 설정

BASE\_DIR = Path(**file**).parent
FRONTEND\_DIR = BASE\_DIR / "frontend"
DATA\_DIR = BASE\_DIR / "data"

# 학생 목록 로드

STUDENT\_CSV = DATA\_DIR / "student\_list.csv"
student\_ids = set()
with open(STUDENT\_CSV, encoding="utf-8") as f:
reader = csv.reader(f)
next(reader, None)
for row in reader:
raw\_id = row\[0].lstrip("\ufeff").strip()
student\_ids.add(raw\_id)

# Flask 애플리케이션 초기화

app = Flask(
**name**,
static\_folder=str(FRONTEND\_DIR),
static\_url\_path=""
)

# SPA 라우팅: 프론트엔드 파일 제공

@app.route("/", defaults={"path": ""})
@app.route("/[path\:path](path:path)")
def serve\_frontend(path):
target = FRONTEND\_DIR / path
if target.exists() and target.is\_file():
return send\_from\_directory(str(FRONTEND\_DIR), path)
return send\_from\_directory(str(FRONTEND\_DIR), "index.html")

# 인증 엔드포인트

@app.route("/api/authenticate")
def authenticate():
user\_id = request.args.get("id", "").strip()
if user\_id in student\_ids:
return jsonify({"authenticated": True})
return jsonify({"authenticated": False, "error": "인증되지 않은 ID입니다."})

# 회차 목록 제공

@app.route("/api/exams")
def list\_exams():
try:
exams = \[d.name for d in DATA\_DIR.iterdir() if d.is\_dir()]
return jsonify({"exams": exams})
except Exception as e:
return jsonify({"error": str(e)}), 500

# 응시 여부 확인

@app.route("/api/check\_exam")
def check\_exam():
exam = request.args.get("exam", "").strip()
user\_id = request.args.get("id", "").strip()
student\_dir = DATA\_DIR / exam / "student\_answer"
if not student\_dir.exists():
return jsonify({"registered": False, "error": "응시 정보가 없습니다."})
for csv\_file in student\_dir.glob("\*.csv"):
with open(csv\_file, encoding="utf-8") as f:
reader = csv.DictReader(f)
for row in reader:
name = row\.get("이름", "").strip()
phone = row\.get("전화번호", "").strip()
digits = "".join(filter(str.isdigit, phone))
identifier = name + digits\[-8:]
if identifier == user\_id:
return jsonify({"registered": True})
return jsonify({"registered": False, "error": "응시 정보가 없습니다."})

# 성적표 이미지 URL 제공

@app.route("/api/reportcard")
def reportcard():
exam = request.args.get("exam", "").strip()
user\_id = request.args.get("id", "").strip()
report\_dir = DATA\_DIR / exam / "report\_card"
if not report\_dir.exists():
return jsonify({"error": "성적표를 찾을 수 없습니다."}), 404
for img in report\_dir.rglob("\*.png"):
if user\_id in img.name:
return jsonify({"url": f"/api/reportcard/image?path={img.as\_posix()}"})
return jsonify({"error": "성적표를 찾을 수 없습니다."}), 404

# 성적표 이미지 서빙

@app.route("/api/reportcard/image")
def reportcard\_image():
path = request.args.get("path", "")
img = Path(path)
if img.exists():
return send\_from\_directory(str(img.parent), img.name)
abort(404)

# 틀린 문제 다시 풀기 & OX 퀴즈 (플레이스홀더)

@app.route("/api/review")
def review():
return jsonify({"error": "미구현 기능입니다."}), 501

@app.route("/api/quiz")
def quiz():
return jsonify({"error": "미구현 기능입니다."}), 501

# 앱 실행

if **name** == "**main**":
app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

```
```
