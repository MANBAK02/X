<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <!-- 모바일 퍼스트 뷰포트 -->
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <title>GAIA 모의고사 복습 사이트</title>
  <style>
    body {
      margin: 0;
      padding: 1rem;
      font-family: sans-serif;
      background: #f9f9f9;
    }
    .container {
      max-width: 400px;
      margin: 0 auto;
      background: white;
      padding: 1rem;
      border-radius: 8px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    h1 {
      margin: 0 0 0.5rem;
      font-size: 1.5rem; /* 제목을 좀 더 키움 */
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .home-button {
      display: flex;
      align-items: center;
      cursor: pointer;
      margin-bottom: 1rem;
      font-size: 16px;
      color: #007bff;
    }
    .home-button img {
      width: 16px;
      height: 16px;
      margin-right: 0.25rem;
    }
    input, select, button {
      display: block;
      width: 100%;
      padding: 0.75rem;
      font-size: 1rem;
      margin: 0.5rem 0;
      box-sizing: border-box;
      border: 1px solid #ccc;
      border-radius: 4px;
    }
    button {
      background: #007bff;
      color: white;
      border: none;
    }
    p.error {
      color: #d00;
      font-size: 0.9rem;
      margin: 0.25rem 0 0;
    }
    /* 메뉴 버튼 */
    .menu-button {
      background: #28a745;
      margin-bottom: 0.75rem;
      color: white;
      font-size: 1rem;
    }
    .menu-button:nth-child(2) { background: #ffc107; }
    .menu-button:nth-child(3) { background: #dc3545; }

    /* 리포트 카드 이미지 */
    .report-img {
      display: block;
      max-width: 100%;
      margin: 0 auto;
    }

    /* GIF (로그인/메인 페이지 상단 로고) */
    .top-gif {
      display: block;
      width: 60%;
      max-width: 200px;
      margin: 0 auto 1rem;
    }

    /* 문제 이미지 */
    .question-img {
      display: block;
      max-width: 100%;
      margin: 0.5rem auto;
    }

    /* 각 섹션 숨김/보이기 */
    .hidden { display: none; }
    .option-label {
      display: block;
      margin: 0.25rem 0;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- “처음으로” 버튼 (로그인/메인 제외 나머지 페이지에서만 보이도록 JS가 제어) -->
    <div id="homeButton" class="home-button hidden">
      <img src="/static/icons/home.png" alt="Home 아이콘" />
      <span>처음으로</span>
    </div>

    <!-- ① 로그인 페이지 -->
    <div id="loginSection">
      <h1>GAIA 모의고사 복습 사이트</h1>
      <img src="/static/globe.gif" alt="Globe 로고" class="top-gif" />
      <input type="text" id="loginId" placeholder="리클래스 ID 입력" />
      <button id="loginBtn">로그인</button>
      <p id="loginMsg" class="error"></p>
    </div>

    <!-- ② 회차 선택 페이지 -->
    <div id="examSection" class="hidden">
      <h1>GAIA 모의고사 복습 사이트</h1>
      <select id="examSelect"></select>
      <button id="examBtn">회차 선택</button>
      <p id="examMsg" class="error"></p>
    </div>

    <!-- ③ 메뉴 페이지 (1. 내 성적표 / 2. 틀린 문제 다시 풀기 / 3. 틀린 문제 OX 퀴즈) -->
    <div id="menuSection" class="hidden">
      <h1>GAIA 모의고사 복습 사이트</h1>
      <button class="menu-button" id="menuReport">1. 내 성적표 확인</button>
      <button class="menu-button" id="menuReview">2. 틀린 문제 다시 풀기</button>
      <button class="menu-button" id="menuQuiz">3. 틀린 문제 O/X 퀴즈</button>
      <p id="menuMsg" class="error"></p>
    </div>

    <!-- ④ 성적표 표시 페이지 -->
    <div id="reportSection" class="hidden">
      <h1>내 성적표</h1>
      <img id="reportImage" class="report-img" alt="성적표 이미지" />
      <p id="reportMsg" class="error"></p>
    </div>

    <!-- ⑤ 틀린 문제 다시 풀기 페이지 -->
    <div id="reviewSection" class="hidden">
      <h1>틀린 문제 다시 풀기</h1>
      <p id="reviewMsg" class="error"></p>
      <!-- 문제 표시 영역 -->
      <div id="questionContainer" class="hidden">
        <img id="questionImage" class="question-img" alt="문제 이미지" />
        <div id="optionsContainer">
          <!-- 옵션 1~5번 라디오 버튼으로 동적 생성 -->
        </div>
        <button id="submitAnswerBtn">제출</button>
        <p id="feedbackMsg"></p>
      </div>
    </div>

    <!-- ⑥ 틀린 문제 OX 퀴즈 페이지 (준비 중) -->
    <div id="quizSection" class="hidden">
      <h1>틀린 문제 O/X 퀴즈 (준비 중)</h1>
    </div>
  </div>

  <script>
    let currentId = "";
    let currentExam = "";
    let wrongQuestions = [];
    let currentQuestionIndex = 0;

    // “처음으로” 버튼 클릭 → 메뉴 페이지로
    document.getElementById("homeButton").onclick = () => {
      // 로그인/회차 선택은 건너뛰고, 바로 “메뉴” 페이지로
      showSection("menuSection");
      hideSection("loginSection");
      hideSection("examSection");
      hideSection("reportSection");
      hideSection("reviewSection");
      hideSection("quizSection");
      document.getElementById("homeButton").classList.remove("hidden");
      clearMessages();
    };

    // 1) 로그인 단계
    document.getElementById("loginBtn").onclick = () => {
      const id = document.getElementById("loginId").value.trim();
      if (!id) {
        return (document.getElementById("loginMsg").textContent = "ID를 입력하세요");
      }
      fetch(`/api/authenticate?id=${encodeURIComponent(id)}`)
        .then((res) =>
          res.json().then((j) => ({
            ok: res.ok,
            ...j
          }))
        )
        .then((data) => {
          if (data.authenticated) {
            currentId = id;
            document.getElementById("loginSection").classList.add("hidden");
            document.getElementById("examSection").classList.remove("hidden");
            document.getElementById("homeButton").classList.add("hidden");
            loadExams();
          } else {
            document.getElementById("loginMsg").textContent =
              "인증되지 않은 ID입니다";
          }
        })
        .catch(() => {
          document.getElementById("loginMsg").textContent =
            "인증 중 오류가 발생했습니다";
        });
    };

    // 2) 회차 목록 불러오기 & 회차 선택
    function loadExams() {
      fetch("/api/exams")
        .then((res) => res.json())
        .then((exams) => {
          const sel = document.getElementById("examSelect");
          sel.innerHTML = "";
          if (exams.length === 0) {
            sel.innerHTML = "<option>등록된 회차가 없습니다</option>";
            return;
          }
          exams.forEach((e) => {
            const opt = document.createElement("option");
            opt.value = e;
            opt.textContent = e;
            sel.appendChild(opt);
          });
        })
        .catch(() => {
          document.getElementById("examMsg").textContent = "회차 목록 로드 실패";
        });
    }

    document.getElementById("examBtn").onclick = () => {
      const exam = document.getElementById("examSelect").value;
      fetch(
        `/api/check_exam?exam=${encodeURIComponent(
          exam
        )}&id=${encodeURIComponent(currentId)}`
      )
        .then((res) =>
          res.json().then((j) => ({
            ok: res.ok,
            ...j
          }))
        )
        .then((data) => {
          if (data.registered) {
            currentExam = exam;
            document.getElementById("examSection").classList.add("hidden");
            document.getElementById("menuSection").classList.remove("hidden");
            document.getElementById("homeButton").classList.remove("hidden");
          } else {
            document.getElementById("examMsg").textContent = data.error;
          }
        })
        .catch(() => {
          document.getElementById("examMsg").textContent =
            "응시 여부 확인 중 오류";
        });
    };

    // 3) 메뉴 버튼 클릭
    document.getElementById("menuReport").onclick = () => {
      // “내 성적표 확인” → /api/reportcard?exam=&id= 호출
      fetch(
        `/api/reportcard?exam=${encodeURIComponent(
          currentExam
        )}&id=${encodeURIComponent(currentId)}`
      )
        .then((res) =>
          res.json().then((j) => ({
            ok: res.ok,
            ...j
          }))
        )
        .then((data) => {
          hideAllSections();
          document.getElementById("reportSection").classList.remove("hidden");
          document.getElementById("homeButton").classList.remove("hidden");
          if (data.url) {
            document.getElementById("reportImage").src = data.url;
            document.getElementById("reportMsg").textContent = "";
          } else {
            document.getElementById("reportMsg").textContent =
              data.error || "성적표를 찾을 수 없습니다.";
          }
        })
        .catch(() => {
          hideAllSections();
          document.getElementById("reportSection").classList.remove("hidden");
          document.getElementById("homeButton").classList.remove("hidden");
          document.getElementById("reportMsg").textContent =
            "성적표 로드 중 오류";
        });
    };

    document.getElementById("menuReview").onclick = () => {
      // 틀린 문제 다시 풀기
      hideAllSections();
      document.getElementById("reviewSection").classList.remove("hidden");
      document.getElementById("homeButton").classList.remove("hidden");
      loadWrongQuestions();
    };

    document.getElementById("menuQuiz").onclick = () => {
      hideAllSections();
      document.getElementById("quizSection").classList.remove("hidden");
      document.getElementById("homeButton").classList.remove("hidden");
    };

    // 4) 틀린 문제 목록 가져오기
    function loadWrongQuestions() {
      document.getElementById("reviewMsg").textContent = "";
      fetch(
        `/api/wrong_questions?exam=${encodeURIComponent(
          currentExam
        )}&id=${encodeURIComponent(currentId)}`
      )
        .then((res) =>
          res.json().then((j) => ({
            ok: res.ok,
            ...j
          }))
        )
        .then((data) => {
          if (data.wrongs && data.wrongs.length > 0) {
            wrongQuestions = data.wrongs;
            currentQuestionIndex = 0;
            showQuestion(); // 첫 번째 틀린 문제부터 표시
          } else if (data.wrongs && data.wrongs.length === 0) {
            document.getElementById("reviewMsg").textContent =
              "틀린 문제가 없습니다!";
          } else {
            document.getElementById("reviewMsg").textContent =
              data.error || "틀린 문제 로드 중 오류";
          }
        })
        .catch(() => {
          document.getElementById("reviewMsg").textContent =
            "틀린 문제 로드 중 오류";
        });
    }

    // 틀린 문제를 화면에 표시
    function showQuestion() {
      const container = document.getElementById("questionContainer");
      container.classList.remove("hidden");
      document.getElementById("feedbackMsg").textContent = "";
      const qnum = wrongQuestions[currentQuestionIndex];
      // 문제 이미지 경로: /static/problem_bank/{exam}/problem_images/{qnum}.png
      document.getElementById("questionImage").src = `/static/problem_bank/${encodeURIComponent(
        currentExam
      )}/problem_images/${qnum}.png`;

      // 옵션 1~5 렌더링
      const opts = document.getElementById("optionsContainer");
      opts.innerHTML = "";
      for (let i = 1; i <= 5; i++) {
        const id = `opt_${i}`;
        const label = document.createElement("label");
        label.className = "option-label";
        label.htmlFor = id;
        label.textContent = `${i}번`;
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "answer";
        radio.id = id;
        radio.value = i;
        label.prepend(radio);
        opts.appendChild(label);
      }
    }

    // 답안 제출
    document.getElementById("submitAnswerBtn").onclick = () => {
      const selected = document.querySelector(
        'input[name="answer"]:checked'
      );
      if (!selected) {
        document.getElementById("feedbackMsg").textContent =
          "먼저 선택하고 제출하세요.";
        return;
      }
      const chosen = selected.value;
      const qnum = wrongQuestions[currentQuestionIndex];
      fetch("/api/submit_answer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          exam: currentExam,
          id: currentId,
          question: qnum,
          answer: chosen
        })
      })
        .then((res) =>
          res.json().then((j) => ({
            ok: res.ok,
            ...j
          }))
        )
        .then((data) => {
          if (data.correct === true) {
            document.getElementById("feedbackMsg").textContent = "정답입니다! 🎉";
          } else {
            document.getElementById("feedbackMsg").textContent =
              `오답입니다. 정답은 ${data.correctAnswer}번입니다.`;
          }
          // 다음 문제로 넘어가려면 1~2초 대기 후 next
          setTimeout(() => {
            currentQuestionIndex++;
            if (currentQuestionIndex < wrongQuestions.length) {
              showQuestion();
            } else {
              document.getElementById("feedbackMsg").textContent =
                "모든 틀린 문제를 확인하셨습니다!";
            }
          }, 1000);
        })
        .catch(() => {
          document.getElementById("feedbackMsg").textContent =
            "제출 중 오류가 발생했습니다.";
        });
    };

    // 공통 함수
    function hideAllSections() {
      [
        "loginSection",
        "examSection",
        "menuSection",
        "reportSection",
        "reviewSection",
        "quizSection"
      ].forEach((id) =>
        document.getElementById(id).classList.add("hidden")
      );
      document
        .getElementById("questionContainer")
        .classList.add("hidden");
    }
    function showSection(id) {
      document.getElementById(id).classList.remove("hidden");
    }
    function hideSection(id) {
      document.getElementById(id).classList.add("hidden");
    }
    function clearMessages() {
      ["loginMsg", "examMsg", "menuMsg", "reportMsg", "reviewMsg"].forEach(
        (id) => {
          document.getElementById(id).textContent = "";
        }
      );
    }
  </script>
</body>
</html>
