from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import auth
from database import get_db
import models
import schemas

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# --- MARK ATTENDANCE (Teacher & Admin) ---
@router.post("/", response_model=schemas.AttendanceResponse, status_code=status.HTTP_201_CREATED)
def mark_attendance(
    attendance: schemas.AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """
    Mark attendance for a student.
    - Teachers can only mark attendance for subjects assigned to them.
    - Admins can mark attendance for any subject.
    - Prevents duplicate attendance entries for the same student, subject, and date.
    """
    # 1. Validate student exists
    student = db.query(models.Student).filter(models.Student.id == attendance.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {attendance.student_id} not found."
        )

    # 2. Validate subject exists
    subject = db.query(models.Subject).filter(models.Subject.id == attendance.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {attendance.subject_id} not found."
        )

    # 3. If teacher, verify that the subject is assigned to this teacher
    if current_user.role.lower() == "teacher" and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You are not the assigned teacher for subject '{subject.subject_name}'."
        )

    # 4. Check for duplicate attendance record
    existing = db.query(models.Attendance).filter(
        models.Attendance.student_id == attendance.student_id,
        models.Attendance.subject_id == attendance.subject_id,
        models.Attendance.attendance_date == attendance.attendance_date,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance already recorded for Student ID {attendance.student_id} in Subject ID {attendance.subject_id} on {attendance.attendance_date}."
        )

    # 5. Create attendance entry
    db_attendance = models.Attendance(
        student_id=attendance.student_id,
        subject_id=attendance.subject_id,
        attendance_date=attendance.attendance_date,
        status=attendance.status,
        marked_by=current_user.id,
    )
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance


# --- GET ATTENDANCE BY ID ---
@router.get("/{attendance_id}", response_model=schemas.AttendanceResponse)
def get_attendance_by_id(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get a single attendance record by ID.
    - Students can only view their own attendance record.
    - Teachers and Admins can view any record.
    """
    record = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance record with ID {attendance_id} not found."
        )

    # If student, verify ownership
    if current_user.role.lower() == "student":
        student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student_profile or record.student_id != student_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own attendance records."
            )

    return record


# --- GET ATTENDANCE FOR A STUDENT ---
@router.get("/student/{student_id}", response_model=list[schemas.AttendanceResponse])
def get_attendance_for_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get all attendance records for a specific student.
    - Students can only view their own records.
    - Teachers and Admins can view records for any student.
    """
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )

    # If student, verify ownership
    if current_user.role.lower() == "student":
        student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student_profile or student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own attendance records."
            )

    records = db.query(models.Attendance).filter(models.Attendance.student_id == student_id).all()
    return records


# --- UPDATE ATTENDANCE (Teacher & Admin) ---
@router.put("/{attendance_id}", response_model=schemas.AttendanceResponse)
def update_attendance(
    attendance_id: int,
    attendance_update: schemas.AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Update an attendance record status or date."""
    db_attendance = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if not db_attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance record with ID {attendance_id} not found."
        )

    # Verify teacher assignment
    subject = db.query(models.Subject).filter(models.Subject.id == db_attendance.subject_id).first()
    if current_user.role.lower() == "teacher" and subject and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not assigned to this subject."
        )

    update_data = attendance_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_attendance, key, value)

    try:
        db.commit()
        db.refresh(db_attendance)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate attendance record exists for this updated date."
        )

    return db_attendance


# --- DELETE ATTENDANCE (Teacher & Admin) ---
@router.delete("/{attendance_id}", status_code=status.HTTP_200_OK)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Delete an attendance record."""
    db_attendance = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if not db_attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance record with ID {attendance_id} not found."
        )

    subject = db.query(models.Subject).filter(models.Subject.id == db_attendance.subject_id).first()
    if current_user.role.lower() == "teacher" and subject and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not assigned to this subject."
        )

    db.delete(db_attendance)
    db.commit()
    return {"message": f"Attendance record ID {attendance_id} successfully deleted."}
