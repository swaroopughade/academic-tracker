from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import auth
from database import get_db
import models
import schemas

router = APIRouter(prefix="/students", tags=["Student Dashboard"])


def build_student_dashboard(student: models.Student, user: models.User, db: Session) -> schemas.StudentDashboardResponse:
    """Helper function to compile the comprehensive academic dashboard for a student."""
    # 1. Fetch subjects for the student's enrolled class and semester
    subjects = db.query(models.Subject).filter(
        models.Subject.student_class == student.student_class,
        models.Subject.semester == student.semester,
    ).all()

    attendance_summaries: list[schemas.SubjectAttendanceSummary] = []
    marks_summaries: list[schemas.SubjectMarksSummary] = []

    grand_total_obtained = 0.0
    grand_total_max = 0.0

    # 2. Process each subject
    for subj in subjects:
        # Attendance calculation
        attendance_records = db.query(models.Attendance).filter(
            models.Attendance.student_id == student.id,
            models.Attendance.subject_id == subj.id,
        ).all()

        total_classes = len(attendance_records)
        present_count = sum(1 for a in attendance_records if a.status.lower() == "present")
        absent_count = sum(1 for a in attendance_records if a.status.lower() == "absent")
        late_count = sum(1 for a in attendance_records if a.status.lower() == "late")

        # Present and Late count as attendance credits
        attended_count = present_count + late_count
        att_percentage = round((attended_count / total_classes) * 100.0, 2) if total_classes > 0 else 0.0

        attendance_summaries.append(
            schemas.SubjectAttendanceSummary(
                subject_id=subj.id,
                subject_code=subj.subject_code,
                subject_name=subj.subject_name,
                total_classes=total_classes,
                present_classes=present_count,
                absent_classes=absent_count,
                late_classes=late_count,
                attendance_percentage=att_percentage,
            )
        )

        # Marks calculation
        exam_records = db.query(models.ExamResult).filter(
            models.ExamResult.student_id == student.id,
            models.ExamResult.subject_id == subj.id,
        ).all()

        exam_items: list[schemas.ExamMarkItem] = []
        subj_obtained = 0.0
        subj_max = 0.0

        for exam in exam_records:
            exam_pct = round((exam.marks_obtained / exam.maximum_marks) * 100.0, 2) if exam.maximum_marks > 0 else 0.0
            exam_items.append(
                schemas.ExamMarkItem(
                    exam_name=exam.exam_name,
                    marks_obtained=exam.marks_obtained,
                    maximum_marks=exam.maximum_marks,
                    percentage=exam_pct,
                    grade=exam.grade,
                )
            )
            subj_obtained += exam.marks_obtained
            subj_max += exam.maximum_marks

        subj_percentage = round((subj_obtained / subj_max) * 100.0, 2) if subj_max > 0 else 0.0
        marks_summaries.append(
            schemas.SubjectMarksSummary(
                subject_id=subj.id,
                subject_code=subj.subject_code,
                subject_name=subj.subject_name,
                exams=exam_items,
                total_obtained=subj_obtained,
                total_maximum=subj_max,
                subject_percentage=subj_percentage,
            )
        )

        grand_total_obtained += subj_obtained
        grand_total_max += subj_max

    # 3. Overall calculation
    overall_percentage = round((grand_total_obtained / grand_total_max) * 100.0, 2) if grand_total_max > 0 else 0.0

    if grand_total_max == 0.0:
        performance_status = "No Data"
    elif overall_percentage >= 85.0:
        performance_status = "Excellent"
    elif overall_percentage >= 65.0:
        performance_status = "Good"
    else:
        performance_status = "Needs Improvement"

    # Subject responses format
    subject_responses = [
        schemas.SubjectResponse(
            id=s.id,
            subject_code=s.subject_code,
            subject_name=s.subject_name,
            student_class=s.student_class,
            semester=s.semester,
            teacher_id=s.teacher_id,
            created_at=s.created_at,
        )
        for s in subjects
    ]

    return schemas.StudentDashboardResponse(
        student_id=student.id,
        user_id=user.id,
        username=user.username,
        full_name=student.full_name,
        roll_number=student.roll_number,
        student_class=student.student_class,
        division=student.division,
        semester=student.semester,
        subjects=subject_responses,
        attendance_summary=attendance_summaries,
        marks_summary=marks_summaries,
        total_marks_obtained=grand_total_obtained,
        total_maximum_marks=grand_total_max,
        overall_percentage=overall_percentage,
        performance_status=performance_status,
    )


# --- LOGGED-IN STUDENT'S DASHBOARD ---
@router.get("/me/dashboard", response_model=schemas.StudentDashboardResponse)
def get_my_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get the personalized academic dashboard for the logged-in student.
    Includes enrolled subjects, attendance rates per subject, marks per exam,
    and cumulative academic status.
    """
    student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for current user account."
        )

    return build_student_dashboard(student_profile, current_user, db)


# --- ADMIN & TEACHER VIEW OF STUDENT DASHBOARD ---
@router.get("/{student_id}/dashboard", response_model=schemas.StudentDashboardResponse)
def get_student_dashboard_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["admin", "teacher"])),
):
    """
    View the academic dashboard of any student.
    Restricted to Teachers and Admins.
    """
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )

    user = db.query(models.User).filter(models.User.id == student.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User account for student ID {student_id} not found."
        )

    return build_student_dashboard(student, user, db)
