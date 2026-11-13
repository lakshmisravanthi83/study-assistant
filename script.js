// ========================================
// BACKEND URL
// ========================================
function getToken() {
    return localStorage.getItem("authToken");
}

function authHeaders(extra = {}) {
    const token = getToken();
    return token ? { ...extra, "Authorization": `Bearer ${token}` } : extra;
}

async function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = "login.html";
        return false;
    }
    try {
        const res = await fetch(`${API_URL}/auth/me`, { headers: authHeaders() });
        if (!res.ok) throw new Error();
        return true;
    } catch {
        localStorage.removeItem("authToken");
        window.location.href = "login.html";
        return false;
    }
}

function logout() {
    localStorage.removeItem("authToken");
    localStorage.removeItem("authUser");
    window.location.href = "login.html";
}
const API_URL = "http://127.0.0.1:8000";


// ========================================
// SECTION NAVIGATION
// ========================================

function showSection(sectionName) {

    const sections = document.querySelectorAll(".section");

    sections.forEach(section => {
        section.classList.remove("active");
    });

    document.getElementById(sectionName).classList.add("active");


    const buttons = document.querySelectorAll(".menu-btn");

    buttons.forEach(button => {
        button.classList.remove("active");
    });


    const sectionTitles = {
        dashboard: ["Good to see you 👋", "Continue your learning journey today."],
        ask: ["Ask AI Tutor 🤖", "Get answers from your study material."],
        upload: ["Upload Study Material 📤", "Add notes to your subjects."],
        plan: ["Your Study Plan 📅", "Plan your preparation effectively."],
        quiz: ["Test Your Knowledge 🧠", "Generate a quiz and challenge yourself."]
    };


    document.getElementById("pageTitle").textContent =
        sectionTitles[sectionName][0];

    document.getElementById("pageSubtitle").textContent =
        sectionTitles[sectionName][1];


    // Highlight corresponding sidebar button

    const menuButtons = document.querySelectorAll(".menu-btn");

    menuButtons.forEach(button => {

        const onclickValue = button.getAttribute("onclick");

        if (onclickValue && onclickValue.includes(sectionName)) {
            button.classList.add("active");
        }

    });
}


// ========================================
// LOAD SUBJECTS
// ========================================

async function loadSubjects() {

    try {

        const response = await fetch(`${API_URL}/subjects`, { headers: authHeaders() });

        if (!response.ok) {
            throw new Error("Unable to load subjects");
        }

        const data = await response.json();

        const subjects = data.subjects || [];


        // Count

        document.getElementById("subjectCount").textContent =
            subjects.length;


        // Sidebar

        const sidebar = document.getElementById("sidebarSubjects");

        sidebar.innerHTML = "";


        if (subjects.length === 0) {

            sidebar.innerHTML =
                `<span class="subject-loading">
                    No subjects yet
                </span>`;

        } else {

            subjects.forEach(subject => {

                const span = document.createElement("span");

                span.className = "subject-tag";

                span.textContent = subject;

                sidebar.appendChild(span);

            });

        }


        // Fill dropdowns

        fillSubjectDropdown("askSubject", subjects);
        fillSubjectDropdown("planSubject", subjects);
        fillSubjectDropdown("quizSubject", subjects);

    }

    catch (error) {

        console.error(error);

        document.getElementById("sidebarSubjects").innerHTML =
            `<span class="subject-loading">
                Backend not connected
            </span>`;
    }
}


// ========================================
// FILL SUBJECT DROPDOWN
// ========================================

function fillSubjectDropdown(id, subjects) {

    const select = document.getElementById(id);

    const currentValue = select.value;

    select.innerHTML =
        `<option value="">Select subject</option>`;


    subjects.forEach(subject => {

        const option = document.createElement("option");

        option.value = subject;
        option.textContent = subject;

        select.appendChild(option);

    });


    if (subjects.includes(currentValue)) {
        select.value = currentValue;
    }
}


// ========================================
// ASK AI
// ========================================

async function askAI() {

    const subject =
        document.getElementById("askSubject").value;

    const question =
        document.getElementById("question").value.trim();


    if (!subject) {
        alert("Please select a subject.");
        return;
    }


    if (!question) {
        alert("Please enter your question.");
        return;
    }


    const answerBox =
        document.getElementById("answerBox");

    const answer =
        document.getElementById("answer");


    answerBox.classList.remove("hidden");

    answer.innerHTML =
        "🤔 AI is thinking...";


    try {

        const url =
            `${API_URL}/ask?subject=${encodeURIComponent(subject)}&question=${encodeURIComponent(question)}`;


        const response = await fetch(url, { headers: authHeaders() });


        if (!response.ok) {
            throw new Error("Unable to get answer");
        }


        const data = await response.json();


        /*
            Your backend result structure may contain
            different fields depending on answer_question().
        */

        if (typeof data === "string") {

            answer.textContent = data;

        } else {

           answer.innerHTML = marked.parse(data.answer || data.response || data.result || JSON.stringify(data, null, 2));
        }

    }

    catch (error) {

        console.error(error);

        answer.textContent =
            "❌ Unable to connect to the backend. Make sure FastAPI is running.";

    }
}


// ========================================
// FILE NAME
// ========================================

function showFileName() {

    const fileInput =
        document.getElementById("fileInput");

    const fileName =
        document.getElementById("fileName");


    if (fileInput.files.length > 0) {

        fileName.textContent =
            "Selected: " + fileInput.files[0].name;

    } else {

        fileName.textContent = "";

    }
}


// ========================================
// UPLOAD FILE
// ========================================

async function uploadFile() {

    const subject =
        document.getElementById("uploadSubject").value.trim();

    const fileInput =
        document.getElementById("fileInput");

    const message =
        document.getElementById("uploadMessage");


    if (!subject) {

        alert("Please enter a subject.");

        return;
    }


    if (fileInput.files.length === 0) {

        alert("Please select a file.");

        return;
    }


    const file =
        fileInput.files[0];


    const formData =
        new FormData();


    formData.append("subject", subject);
    formData.append("file", file);


    message.textContent =
        "Uploading and processing...";


    try {

       const response =
    await fetch(`${API_URL}/upload`, {

        method: "POST",

        headers: authHeaders(),

        body: formData

    });

        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "Upload failed"
            );

        }


        message.textContent =
            `✅ ${data.filename} uploaded successfully. ${data.chunks_added} chunks added.`;


        // Refresh subjects

        await loadSubjects();


        // Clear fields

        document.getElementById("uploadSubject").value = "";

        fileInput.value = "";

        document.getElementById("fileName").textContent = "";

    }

    catch (error) {

        console.error(error);

        message.textContent =
            "❌ " + error.message;

    }
}


// ========================================
// GENERATE STUDY PLAN
// ========================================

async function generatePlan() {

    const subject =
        document.getElementById("planSubject").value;

    const examDate =
        document.getElementById("examDate").value;

    const resultBox =
        document.getElementById("planResult");


    if (!subject) {

        alert("Please select a subject.");

        return;
    }


    if (!examDate) {

        alert("Please select your exam date.");

        return;
    }


    resultBox.classList.remove("hidden");

    resultBox.textContent =
        "📅 Creating your study plan...";


    try {

        const url =
            `${API_URL}/plan?subject=${encodeURIComponent(subject)}&exam_date=${encodeURIComponent(examDate)}`;


        const response =
    await fetch(url, {

        method: "POST",

        headers: authHeaders()

    });


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "Could not create plan"
            );

        }

        resultBox.innerHTML = renderPlan(data);

    }

    catch (error) {

        console.error(error);

        resultBox.textContent =
            "❌ " + error.message;

    }
}


// ========================================
// GENERATE QUIZ
// ========================================

async function generateQuiz() {

    const subject =
        document.getElementById("quizSubject").value;

    const topicsText =
        document.getElementById("quizTopics").value.trim();

    const count =
        Number(
            document.getElementById("questionCount").value
        );


    const quizContainer =
        document.getElementById("quizResult");


    if (!subject) {

        alert("Please select a subject.");

        return;
    }


    if (!topicsText) {

        alert("Please enter at least one topic.");

        return;
    }


    const topics =
        topicsText
            .split(",")
            .map(topic => topic.trim())
            .filter(topic => topic.length > 0);


    quizContainer.classList.remove("hidden");

    quizContainer.innerHTML =
        "<div class='card'>🧠 Generating quiz...</div>";


    try {

        const response =
    await fetch(`${API_URL}/quiz/generate`, {

        method: "POST",

        headers: authHeaders({
            "Content-Type": "application/json"
        }),

        body: JSON.stringify({
            subject: subject,
            topics: topics,
            n_questions: count
        })

    });


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "Quiz generation failed"
            );

        }


        displayQuiz(data);

    }

    catch (error) {

        console.error(error);

        quizContainer.innerHTML =
            `<div class="card">
                ❌ ${error.message}
            </div>`;

    }
}


// ========================================
// DISPLAY QUIZ
// ========================================

function displayQuiz(data) {

    const container =
        document.getElementById("quizResult");

    const questions =
        data.questions || data.quiz || [];

    if (!Array.isArray(questions) || questions.length === 0) {

        container.innerHTML =
            `<div class="card">
                <h3>Quiz generated</h3>
                <pre>${escapeHTML(
                    JSON.stringify(data, null, 2)
                )}</pre>
            </div>`;

        return;
    }

    let html = "";

    questions.forEach((question, index) => {

        const questionText =
            question.question || `Question ${index + 1}`;

        // Backend returns options as {a: "...", b: "...", c: "...", d: "..."},
        // not an array — iterate its entries instead.
        const options = question.options || {};

        html += `
            <div class="quiz-question">
                <h3>${index + 1}. ${escapeHTML(questionText)}</h3>
        `;

        Object.entries(options).forEach(([key, text]) => {

            html += `
                <label class="option">
                    <input
                        type="radio"
                        name="${question.id}"
                        value="${key}"
                    >
                    ${key.toUpperCase()}. ${escapeHTML(String(text))}
                </label>
            `;

        });

        html += `</div>`;

    });

    html += `
        <button
            class="primary-btn submit-quiz"
            onclick="submitQuiz()"
        >
            Submit Quiz ✓
        </button>
    `;

    container.innerHTML = html;

    if (data.quiz_id) {
        container.dataset.quizId = data.quiz_id;
    }
}


// ========================================
// SUBMIT QUIZ
// ========================================

async function submitQuiz() {

    const container =
        document.getElementById("quizResult");


    const quizId =
        container.dataset.quizId;


    if (!quizId) {

        alert(
            "Quiz ID was not returned by the backend."
        );

        return;
    }


    const answers = {};


    const selected =
        container.querySelectorAll(
            "input[type='radio']:checked"
        );


    selected.forEach(input => {

        answers[input.name] =
            input.value;

    });


    try {

        const response =
            await fetch(`${API_URL}/quiz/submit`, {

                method: "POST",

                headers: authHeaders( {
                    "Content-Type": "application/json"
                }),

                body: JSON.stringify({

                    quiz_id: quizId,

                    answers: answers

                })

            });


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "Quiz submission failed"
            );

        }


        container.innerHTML = renderQuizResults(data);
            

    }

    catch (error) {

        alert(error.message);

    }
}


// ========================================
// FORMAT OBJECT
// ========================================

function formatObject(data) {

    if (typeof data === "string") {
        return data;
    }


    return JSON.stringify(
        data,
        null,
        2
    );
}


// ========================================
// ESCAPE HTML
// ========================================

function escapeHTML(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


// ========================================
// INITIAL LOAD
// ========================================
document.addEventListener("DOMContentLoaded", async function () {
    const ok = await checkAuth();
    if (ok) loadSubjects();
});

// ========================================
// RENDER STUDY PLAN
// ========================================

function renderPlan(data) {

    if (data.error) {
        return "❌ " + escapeHTML(data.error);
    }

    let html = `
        <h3>📚 Topics Covered</h3>
        <p>${escapeHTML((data.topics || []).join(", "))}</p>
        <h3>🗓️ Day-wise Plan</h3>
    `;

    (data.plan || []).forEach(day => {

        html += `
            <div class="quiz-question">
                <h3>Day ${day.day}${day.date ? " — " + escapeHTML(day.date) : ""}</h3>
                <p><strong>${escapeHTML(day.focus || "")}</strong></p>
                <ul>
                    ${(day.topics || []).map(t => `<li>${escapeHTML(t)}</li>`).join("")}
                </ul>
            </div>
        `;

    });

        return html.replace(/>\s+</g, "><").trim();
}


// ========================================
// RENDER QUIZ RESULTS
// ========================================

function renderQuizResults(data) {

    let html = `
        <div class="card">
            <h2>🎉 Quiz Completed!</h2>
            <p><strong>Score: ${data.correct} / ${data.total}</strong></p>
    `;

    if (data.weak_topics && data.weak_topics.length > 0) {
        html += `<p>⚠️ Topics to review: ${escapeHTML(data.weak_topics.join(", "))}</p>`;
    } else {
        html += `<p>✅ No weak topics — nice work!</p>`;
    }

    html += `</div>`;

    (data.results || []).forEach(r => {

        const icon = r.correct ? "✅" : "❌";

        html += `
            <div class="quiz-question">
                <h3>${icon} ${escapeHTML(r.topic)}</h3>
                <p>Your answer: <strong>${escapeHTML(r.your_answer || "(none)")}</strong> |
                   Correct answer: <strong>${escapeHTML(r.correct_option)}</strong></p>
                <p>${escapeHTML(r.explanation)}</p>
            </div>
        `;

    });

    return html;
}