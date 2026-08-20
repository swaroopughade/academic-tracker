// student_dashboard.js
// Fetches personalized student attendance, marks, alerts, and renders a Chart.js graph

const API_BASE_URL = "http://127.0.0.1:8000";

// 1. Authentication Check: Ensure token exists before loading page
const token = localStorage.getItem("access_token");
if (!token) {
    // If not logged in, redirect immediately to login page
    window.location.href = "login.html";
}

// 2. Setup Logout Button
document.getElementById("logoutBtn").addEventListener("click", () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("role");
    localStorage.removeItem("username");
    localStorage.removeItem("student_id");
    window.location.href = "login.html";
});

// 3. Main Dashboard Loader
async function loadStudentDashboard() {
    try {
        // --- Fetch Comprehensive Student Dashboard ---
        // Attaching Authorization Header: Bearer <token>
        const response = await fetch(`${API_BASE_URL}/students/me/dashboard`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json",
            },
        });

        if (response.status === 401 || response.status === 403) {
            // Token expired or unauthorized
            alert("Session expired or unauthorized. Please log in again.");
            localStorage.clear();
            window.location.href = "login.html";
            return;
        }

        if (!response.ok) {
            const errData = await response.json();
            document.getElementById("studentInfo").innerHTML = `<p style="color:red;">Error: ${errData.detail || "Could not load dashboard data."}</p>`;
            return;
        }

        const data = await response.json();

        // 4. Store/update student_id in localStorage for alerts endpoint
        const studentId = data.student_id;
        localStorage.setItem("student_id", studentId);

        // 5. Render Student Information Card
        document.getElementById("welcomeUser").textContent = `Logged in as: ${data.full_name} (${data.username})`;
        document.getElementById("studentInfo").innerHTML = `
            <p><strong>Name:</strong> ${data.full_name} | <strong>Roll No:</strong> ${data.roll_number}</p>
            <p><strong>Class:</strong> ${data.student_class} | <strong>Division:</strong> ${data.division} | <strong>Semester:</strong> ${data.semester}</p>
            <p><strong>Overall Marks %:</strong> ${data.overall_percentage}% | <strong>Status:</strong> <span class="status-badge" style="background:#e0f2fe; color:#0369a1;">${data.performance_status}</span></p>
        `;

        // 6. Render Attendance Table
        const attendanceTbody = document.getElementById("attendanceTableBody");
        if (data.attendance_summary && data.attendance_summary.length > 0) {
            attendanceTbody.innerHTML = data.attendance_summary.map(item => `
                <tr>
                    <td>${item.subject_code}</td>
                    <td>${item.subject_name}</td>
                    <td>${item.total_classes}</td>
                    <td>${item.present_classes}</td>
                    <td>${item.absent_classes}</td>
                    <td>${item.late_classes}</td>
                    <td style="font-weight:bold; color: ${item.attendance_percentage < 75 ? '#dc2626' : '#16a34a'};">
                        ${item.attendance_percentage}%
                    </td>
                </tr>
            `).join("");
        } else {
            attendanceTbody.innerHTML = `<tr><td colspan="7">No attendance records found for enrolled subjects.</td></tr>`;
        }

        // 7. Render Marks Table
        const marksTbody = document.getElementById("marksTableBody");
        const chartLabels = [];
        const chartValues = [];

        let allExamsList = [];
        if (data.marks_summary && data.marks_summary.length > 0) {
            data.marks_summary.forEach(sub => {
                if (sub.exams && sub.exams.length > 0) {
                    sub.exams.forEach(ex => {
                        allExamsList.push({
                            subject_name: sub.subject_name,
                            exam_name: ex.exam_name,
                            marks_obtained: ex.marks_obtained,
                            maximum_marks: ex.maximum_marks,
                            percentage: ex.percentage,
                            grade: ex.grade,
                        });
                        // Prepare data points for chart
                        chartLabels.push(`${sub.subject_name} (${ex.exam_name})`);
                        chartValues.push(ex.percentage);
                    });
                }
            });
        }

        if (allExamsList.length > 0) {
            marksTbody.innerHTML = allExamsList.map(item => `
                <tr>
                    <td>${item.subject_name}</td>
                    <td>${item.exam_name}</td>
                    <td>${item.marks_obtained}</td>
                    <td>${item.maximum_marks}</td>
                    <td>${item.percentage}%</td>
                    <td><strong>${item.grade}</strong></td>
                </tr>
            `).join("");
        } else {
            marksTbody.innerHTML = `<tr><td colspan="6">No exam marks records found.</td></tr>`;
        }

        // 8. Fetch and Render Smart Alerts
        await loadStudentAlerts(studentId);

        // 9. Render Chart.js Graph
        renderMarksChart(chartLabels, chartValues);

    } catch (error) {
        console.error("Dashboard loading error:", error);
        document.getElementById("studentInfo").innerHTML = `<p style="color:red;">Error connecting to API server.</p>`;
    }
}

// Helper to fetch and display alerts
async function loadStudentAlerts(studentId) {
    const alertsContainer = document.getElementById("alertsContainer");
    try {
        const res = await fetch(`${API_BASE_URL}/alerts/${studentId}`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`,
            },
        });

        if (!res.ok) {
            alertsContainer.innerHTML = `<p>Unable to load alerts.</p>`;
            return;
        }

        const data = await res.json();
        if (!data.alerts || data.alerts.length === 0) {
            alertsContainer.innerHTML = `<div class="alert-box info" style="background:#e0f2fe; border-color:#bae6fd; color:#0369a1;">✅ No active alerts at this time. All academic requirements are on track!</div>`;
            return;
        }

        alertsContainer.innerHTML = data.alerts.map(a => {
            let badge = "⚠️ Alert";
            let boxClass = "alert-box";

            if (a.alert_type === "attendance_shortage") {
                badge = "⚠️ Shortage Warning";
                boxClass = "alert-box danger";
            } else if (a.alert_type === "deadline_reminder") {
                badge = "🕒 Deadline Reminder";
                boxClass = "alert-box";
            } else if (a.alert_type === "performance_warning") {
                badge = "🚨 Performance Warning";
                boxClass = "alert-box danger";
            }

            return `
                <div class="${boxClass}">
                    <strong>${badge}:</strong> ${a.message}
                </div>
            `;
        }).join("");

    } catch (err) {
        console.error("Alerts fetch error:", err);
        alertsContainer.innerHTML = `<p>Error fetching alerts.</p>`;
    }
}

// Helper to render simple Chart.js Bar Chart
function renderMarksChart(labels, values) {
    const ctx = document.getElementById("marksChart").getContext("2d");

    // If no exam data exists, provide a sample visual indicator
    const displayLabels = labels.length > 0 ? labels : ["No Exams Yet"];
    const displayValues = values.length > 0 ? values : [0];

    new Chart(ctx, {
        type: "bar",
        data: {
            labels: displayLabels,
            datasets: [{
                label: "Marks Percentage (%)",
                data: displayValues,
                backgroundColor: displayValues.map(v => v < 40 ? "rgba(239, 68, 68, 0.7)" : "rgba(59, 130, 246, 0.7)"),
                borderColor: displayValues.map(v => v < 40 ? "rgba(239, 68, 68, 1)" : "rgba(59, 130, 246, 1)"),
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: "Score (%)",
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                }
            }
        }
    });
}

// Run on page load
loadStudentDashboard();
