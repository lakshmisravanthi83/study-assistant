const API_URL = "http://127.0.0.1:8000";
let mode = "login";

// If already logged in, skip straight to the app
if (localStorage.getItem("authToken")) {
    window.location.href = "index.html";
}

function toggleMode() {
    mode = mode === "login" ? "register" : "login";

    document.getElementById("nameField").classList.toggle("hidden", mode === "login");
    document.getElementById("formTitle").textContent = mode === "login" ? "Welcome back" : "Create your account";
    document.getElementById("formSubtitle").textContent =
        mode === "login" ? "Log in to continue your learning journey." : "Start your personalized learning journey.";
    document.getElementById("submitBtn").textContent = mode === "login" ? "Log In" : "Register";
    document.getElementById("toggleText").textContent = mode === "login" ? "Don't have an account?" : "Already have an account?";
    document.getElementById("toggleLink").textContent = mode === "login" ? "Register" : "Log In";
    document.getElementById("errorMsg").classList.add("hidden");
}

async function handleSubmit() {
    const email = document.getElementById("emailInput").value.trim();
    const password = document.getElementById("passwordInput").value;
    const name = document.getElementById("nameInput").value.trim();
    const errorMsg = document.getElementById("errorMsg");
    errorMsg.classList.add("hidden");

    if (!email || !password) {
        errorMsg.textContent = "Please fill in email and password.";
        errorMsg.classList.remove("hidden");
        return;
    }

    const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
    const body = mode === "login" ? { email, password } : { email, password, name };

    try {
        const res = await fetch(`${API_URL}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Something went wrong");
        }

        localStorage.setItem("authToken", data.token);
        localStorage.setItem("authUser", JSON.stringify(data.user));
        window.location.href = "index.html";

    } catch (err) {
        errorMsg.textContent = "❌ " + err.message;
        errorMsg.classList.remove("hidden");
    }
}