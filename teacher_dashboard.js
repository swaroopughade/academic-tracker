// teacher_dashboard.js
// Handles student list retrieval, subjects directory, and marking student attendance

const API_BASE_URL = "http://127.0.0.1:8000";

// 1. Authentication Check
const token = localStorage.getItem("access_token");
const role = localStorage.getItem("role") || "";
const username = localStorage.getItem("username") || "Teacher";

if (!token) {
    window.location.href = "login.html";
}

document.getElementById("welcomeUser").textContent = `Logged in as: ${username} (Role: ${role.toUpperCase()})`;

// 2. Setup Logout Button
document.getElementById("logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("role");
    localStorage.removeItem("username");
    localStorage.removeItem("student_id");
    window.location.href = "login.html";
});

// 3. Set default date in Attendance form to today (YYYY-MM-DD)
const todayDateStr = new Date().toISOString().split("T")[0];
document.getElementById("attendanceDateInput").value = todayDateStr;

// 4. Load Students List
async function loadStudents() {
    const tbody = document.getElementById("studentsTableBody");
    try {
        const res = await fetch(`${API_BASE_URL}/students/`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
            },
        });

        if (res.status === 401 || res.status === 403) {
            alert("Session expired or unauthorized. Please log in again.");
            localStorage.clear();
            window.location.href = "login.html";
            return;
        }

        if (!res.ok) {
            tbody.innerHTML = `<tr><td colspan="6" style="color:red;">Error loading students.</td></tr>`;
            return;
        }

        const students = await res.json();
        if (students.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6">No student profiles found. Create some in the database or Swagger.</td></tr>`;
            return;
        }

        tbody.innerHTML = students.map(s => `
            <tr>
                <td><strong>${s.id}</strong></td>
                <td>${s.full_name}</td>
                <td>${s.roll_number}</td>
                <td>${s.student_class}</td>
                <td>${s.division}</td>
                <td>${s.semester}</td>
            </tr>
        `).join("");

    } catch (err) {
        console.error("Fetch students error:", err);
        tbody.innerHTML = `<tr><td colspan="6" style="color:red;">Connection error fetching students.</td></tr>`;
    }
}

// 5. Load Subjects List
async function loadSubjects() {
    const tbody = document.getElementById("subjectsTableBody");
    try {
        const res = await fetch(`${API_BASE_URL}/subjects/`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
            },
        });

        if (!res.ok) {
            tbody.innerHTML = `<tr><td colspan="6" style="color:red;">Error loading subjects.</td></tr>`;
            return;
        }

        const subjects = await res.json();
        if (subjects.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6">No subjects found.</td></tr>`;
            return;
        }

        tbody.innerHTML = subjects.map(sub => `
            <tr>
                <td><strong>${sub.id}</strong></td>
                <td>${sub.subject_code}</td>
                <td>${sub.subject_name}</td>
                <td>${sub.student_class}</td>
                <td>${sub.semester}</td>
                <td>${sub.teacher_id !== null ? sub.teacher_id : "None"}</td>
            </tr>
        `).join("");

    } catch (err) {
        console.error("Fetch subjects error:", err);
        tbody.innerHTML = `<tr><td colspan="6" style="color:red;">Connection error fetching subjects.</td></tr>`;
    }
}

// 6. Handle Attendance Form Submission
const attendanceForm = document.getElementById("attendanceForm");
const attendanceMessage = document.getElementById("attendanceMessage");

attendanceForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    attendanceMessage.className = "message-box";
    attendanceMessage.style.display = "none";
    attendanceMessage.textContent = "";

    const studentId = parseInt(document.getElementById("studentIdInput").value, 10);
    const subjectId = parseInt(document.getElementById("subjectIdInput").value, 10);
    const statusVal = document.getElementById("statusSelect").value;
    const dateVal = document.getElementById("attendanceDateInput").value;

    if (!studentId || !subjectId || !dateVal) {
        showMessage("Please fill out all fields.", "error");
        return;
    }

    try {
        // Send POST request with JSON payload and Authorization Bearer header
        const res = await fetch(`${API_BASE_URL}/attendance/`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                student_id: studentId,
                subject_id: subjectId,
                status: statusVal,
                attendance_date: dateVal,
            }),
        });

        const data = await res.json();

        if (!res.ok) {
            showMessage(data.detail || "Failed to record attendance.", "error");
            return;
        }

        showMessage(`✅ Attendance successfully marked as "${data.status}" for Student ID ${data.student_id} on ${data.attendance_date}!`, "success");

    } catch (err) {
        console.error("Submit attendance error:", err);
        showMessage("Network error. Make sure the backend server is running.", "error");
    }
});

function showMessage(msg, type) {
    attendanceMessage.textContent = msg;
    attendanceMessage.className = `message-box ${type}`;
    attendanceMessage.style.display = "block";
}

// Initialize tables on page load
loadStudents();
loadSubjects();
