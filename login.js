// login.js
// Handles client-side authentication against the FastAPI /login endpoint

const API_BASE_URL = "http://127.0.0.1:8000";

// Grab DOM elements
const loginForm = document.getElementById("loginForm");
const errorMessage = document.getElementById("errorMessage");

loginForm.addEventListener("submit", async function (event) {
    // 1. Prevent default page reload on form submit
    event.preventDefault();
    errorMessage.textContent = "";

    // 2. Read values from input fields
    const usernameInput = document.getElementById("username").value.trim();
    const passwordInput = document.getElementById("password").value;

    if (!usernameInput || !passwordInput) {
        errorMessage.textContent = "Please enter both username and password.";
        return;
    }

    try {
        // 3. FastAPI's OAuth2PasswordRequestForm expects URL-encoded form data (not raw JSON)
        const formData = new URLSearchParams();
        formData.append("username", usernameInput);
        formData.append("password", passwordInput);

        // 4. Send POST request to /login endpoint
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: formData,
        });

        const data = await response.json();

        // 5. Handle response errors (e.g. 401 Unauthorized)
        if (!response.ok) {
            errorMessage.textContent = data.detail || "Login failed. Please check your credentials.";
            return;
        }

        // 6. On success: Store auth tokens and user info in localStorage
        // localStorage persists even if the user refreshes or navigates between pages
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("role", data.role || "student");
        localStorage.setItem("username", usernameInput);
        if (data.student_id) {
            localStorage.setItem("student_id", data.student_id);
        } else {
            localStorage.removeItem("student_id");
        }

        // 7. Role-based redirect: Send the user to their appropriate dashboard
        const role = (data.role || "").toLowerCase();
        if (role === "student") {
            window.location.href = "student_dashboard.html";
        } else if (role === "teacher" || role === "admin") {
            window.location.href = "teacher_dashboard.html";
        } else {
            // Default fallback
            window.location.href = "student_dashboard.html";
        }
    } catch (error) {
        console.error("Login network error:", error);
        errorMessage.textContent = "Unable to connect to server. Make sure the backend (uvicorn) is running on http://127.0.0.1:8000.";
    }
});
