"""
routers/alerts.py
GET /alerts/{student_id}

Returns ALL active alerts for a student in a single response:
  1. attendance_shortage  — any subject where attendance < 75 %
  2. deadline_reminder    — assignments due within 2 days and not yet submitted
  3. performance_warning  — any Exam mark below 40 %
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import auth
from database import get_db
import models
import schemas

router = APIRouter(tags=["Smart Alerts"])


@router.get("/alerts/{student_id}", response_model=schemas.StudentAlertsResponse)
def get_student_alerts(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Returns all active alerts for a given student.

    Alert types returned:
    - attendance_shortage   : attendance < 75 % in any subject
    - deadline_reminder     : assignment deadline within 2 days, not yet submitted
    - performance_warning   : score < 40 % in any exam (Day-3 Marks model)

    Access:
    - Students can only view their OWN alerts.
    - Teachers and Admins can view any student's alerts.
    """

    # 1. Fetch the student profile
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )

    # 2. Students can only check their own alerts
    if current_user.role.lower() == "student":
        my_profile = db.query(models.Student).filter(
            models.Student.user_id == current_user.id
        ).first()
        if not my_profile or my_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own alerts.",
            )

    alerts: list[schemas.AlertItem] = []

    # -------------------------------------------------------------------
    # ALERT TYPE 1: Attendance Shortage (< 75 % in any subject)
    # -------------------------------------------------------------------
    subjects = db.query(models.Subject).filter(
        models.Subject.student_class == student.student_class,
        models.Subject.semester == student.semester,
    ).all()

    for subj in subjects:
        records = db.query(models.Attendance).filter(
            models.Attendance.student_id == student.id,
            models.Attendance.subject_id == subj.id,
        ).all()

        total = len(records)
        if total == 0:
            # No attendance data yet — skip (no false alarm)
            continue

        # Present + Late both count as "attended"
        attended = sum(1 for r in records if r.status.lower() in ("present", "late"))
        percentage = (attended / total) * 100.0

        if percentage < 75.0:
            alerts.append(
                schemas.AlertItem(
                    alert_type="attendance_shortage",
                    message=(
                        f"Low attendance in '{subj.subject_name}' ({subj.subject_code}): "
                        f"{percentage:.1f}% attended out of {total} classes. "
                        f"Minimum required is 75%."
                    ),
                )
            )

    # -------------------------------------------------------------------
    # ALERT TYPE 2: Deadline Reminder
    # Assignment due within 2 days AND student has NOT submitted it yet
    # -------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc)
    two_days_later = now_utc + timedelta(days=2)

    # Get all assignment IDs for subjects in this student's class/semester
    subject_ids = [s.id for s in subjects]

    upcoming_assignments = db.query(models.Assignment).filter(
        models.Assignment.subject_id.in_(subject_ids),
        # Deadline is in the future but within 2 days
        models.Assignment.deadline > now_utc,
        models.Assignment.deadline <= two_days_later,
    ).all()

    for assignment in upcoming_assignments:
        # Check if this student has a submission record marked as submitted
        submission = db.query(models.AssignmentSubmission).filter(
            models.AssignmentSubmission.assignment_id == assignment.id,
            models.AssignmentSubmission.student_id == student.id,
            models.AssignmentSubmission.submitted == True,   # noqa: E712
        ).first()

        if not submission:
            # No submission yet — fire the alert
            # Calculate hours remaining
            deadline_aware = assignment.deadline
            if deadline_aware.tzinfo is None:
                # If deadline stored without timezone info, assume UTC
                deadline_aware = deadline_aware.replace(tzinfo=timezone.utc)

            hours_left = (deadline_aware - now_utc).total_seconds() / 3600
            alerts.append(
                schemas.AlertItem(
                    alert_type="deadline_reminder",
                    message=(
                        f"Assignment '{assignment.title}' is due in "
                        f"{hours_left:.1f} hours and has NOT been submitted yet."
                    ),
                )
            )

    # -------------------------------------------------------------------
    # ALERT TYPE 3: Performance Warning
    # Score below 40 % in any exam (uses Day-3 Mark model)
    # -------------------------------------------------------------------
    marks = db.query(models.Mark).filter(
        models.Mark.student_id == student.id
    ).all()

    for mark in marks:
        exam = db.query(models.Exam).filter(models.Exam.id == mark.exam_id).first()
        if not exam or exam.max_marks <= 0:
            continue

        percentage = (mark.score / exam.max_marks) * 100.0
        if percentage < 40.0:
            alerts.append(
                schemas.AlertItem(
                    alert_type="performance_warning",
                    message=(
                        f"Low performance in exam '{exam.name}': scored "
                        f"{mark.score}/{exam.max_marks} ({percentage:.1f}%). "
                        f"Minimum passing threshold is 40%."
                    ),
                )
            )

    return schemas.StudentAlertsResponse(
        student_id=student.id,
        full_name=student.full_name,
        alerts=alerts,
    )
