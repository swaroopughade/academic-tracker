from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import auth
from database import get_db
import models
import schemas

router = APIRouter(prefix="/subjects", tags=["Subjects"])


# --- CREATE SUBJECT (Admin only) ---
@router.post("/", response_model=schemas.SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    subject: schemas.SubjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin")),
):
    """
    Create a new subject. Only Admins are authorized.
    Validates teacher role and prevents duplicate subject codes for the same class and semester.
    """
    # 1. Validate teacher if assigned
    if subject.teacher_id is not None:
        teacher = db.query(models.User).filter(models.User.id == subject.teacher_id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher with user ID {subject.teacher_id} not found."
            )
        if teacher.role.lower() not in ["teacher", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User ID {subject.teacher_id} has role '{teacher.role}', not 'teacher'."
            )

    # 2. Check for duplicate subject code for the class & semester
    existing = db.query(models.Subject).filter(
        models.Subject.subject_code == subject.subject_code,
        models.Subject.student_class == subject.student_class,
        models.Subject.semester == subject.semester,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject code '{subject.subject_code}' already exists for class '{subject.student_class}' and semester '{subject.semester}'."
        )

    # 3. Create and save subject
    db_subject = models.Subject(**subject.model_dump())
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject


# --- GET ALL SUBJECTS ---
@router.get("/", response_model=list[schemas.SubjectResponse])
def get_all_subjects(
    student_class: str | None = None,
    semester: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Fetch subjects.
    - Students automatically see only subjects for their enrolled class & semester.
    - Teachers and Admins can view all subjects, or filter by class/semester query parameters.
    """
    query = db.query(models.Subject)

    # If student, restrict to their class and semester
    if current_user.role.lower() == "student":
        student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for the current user."
            )
        query = query.filter(
            models.Subject.student_class == student_profile.student_class,
            models.Subject.semester == student_profile.semester
        )
    else:
        # Teachers and Admins can optionally filter by query params
        if student_class:
            query = query.filter(models.Subject.student_class == student_class)
        if semester:
            query = query.filter(models.Subject.semester == semester)

    return query.all()


# --- GET SINGLE SUBJECT BY ID ---
@router.get("/{subject_id}", response_model=schemas.SubjectResponse)
def get_subject_by_id(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch details of a single subject by ID."""
    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )
    return subject


# --- UPDATE SUBJECT (Admin only) ---
@router.put("/{subject_id}", response_model=schemas.SubjectResponse)
def update_subject(
    subject_id: int,
    subject_update: schemas.SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin")),
):
    """Update subject details. Only Admins are authorized."""
    db_subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not db_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    update_data = subject_update.model_dump(exclude_unset=True)

    # Validate teacher if updated
    if "teacher_id" in update_data and update_data["teacher_id"] is not None:
        teacher = db.query(models.User).filter(models.User.id == update_data["teacher_id"]).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher with user ID {update_data['teacher_id']} not found."
            )
        if teacher.role.lower() not in ["teacher", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User ID {update_data['teacher_id']} has role '{teacher.role}', not 'teacher'."
            )

    # Check duplicate constraint if code, class, or semester is updated
    new_code = update_data.get("subject_code", db_subject.subject_code)
    new_class = update_data.get("student_class", db_subject.student_class)
    new_semester = update_data.get("semester", db_subject.semester)

    existing = db.query(models.Subject).filter(
        models.Subject.id != subject_id,
        models.Subject.subject_code == new_code,
        models.Subject.student_class == new_class,
        models.Subject.semester == new_semester,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject code '{new_code}' already exists for class '{new_class}' and semester '{new_semester}'."
        )

    for key, value in update_data.items():
        setattr(db_subject, key, value)

    try:
        db.commit()
        db.refresh(db_subject)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity constraint violation during subject update."
        )

    return db_subject


# --- DELETE SUBJECT (Admin only) ---
@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("admin")),
):
    """Delete a subject. Only Admins are authorized."""
    db_subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not db_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    db.delete(db_subject)
    db.commit()
    return {"message": f"Subject '{db_subject.subject_name}' (ID: {subject_id}) successfully deleted."}
