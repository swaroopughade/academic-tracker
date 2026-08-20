"""
routers/exams.py
Handles Exam creation and Mark entry/retrieval.

Authorization rules:
  - Create / Update Exam        → Teacher or Admin only
  - Enter / Update Mark         → Teacher or Admin only (teacher must own the subject)
  - GET marks for a student     → that student (their own), or Teacher/Admin
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import auth
from database import get_db
import models
import schemas

router = APIRouter(tags=["Exams & Marks"])


# ---------------------------------------------------------------------------
# GRADE HELPER — calculated on-the-fly, NOT stored in DB
# ---------------------------------------------------------------------------

def calculate_grade(score: float, max_marks: float) -> str:
    """Return letter grade based on percentage."""
    if max_marks <= 0:
        return "N/A"
    pct = (score / max_marks) * 100
    if pct >= 90:
        return "A+"
    if pct >= 75:
        return "A"
    if pct >= 60:
        return "B"
    if pct >= 40:
        return "C"
    return "Fail"


def build_mark_response(mark: models.Mark, exam: models.Exam) -> schemas.MarkResponse:
    """Build a MarkResponse, calculating grade and percentage on-the-fly."""
    pct = round((mark.score / exam.max_marks) * 100, 2) if exam.max_marks > 0 else 0.0
    grade = calculate_grade(mark.score, exam.max_marks)
    return schemas.MarkResponse(
        id=mark.id,
        student_id=mark.student_id,
        exam_id=mark.exam_id,
        score=mark.score,
        grade=grade,
        percentage=pct,
        entered_by=mark.entered_by,
        created_at=mark.created_at,
    )


# ===========================================================================
# EXAM ENDPOINTS
# ===========================================================================

@router.post("/exams/", response_model=schemas.ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    exam: schemas.ExamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """
    Create a new exam for a subject.
    Teachers can only create exams for their own subject.
    Admins can create exams for any subject.
    """
    # 1. Verify subject exists
    subject = db.query(models.Subject).filter(models.Subject.id == exam.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {exam.subject_id} not found.",
        )

    # 2. Teachers can only create exams for their assigned subject
    if current_user.role.lower() == "teacher" and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not the assigned teacher for subject '{subject.subject_name}'.",
        )

    # 3. Prevent duplicate exam name in the same subject
    existing = db.query(models.Exam).filter(
        models.Exam.name == exam.name,
        models.Exam.subject_id == exam.subject_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An exam named '{exam.name}' already exists for this subject.",
        )

    # 4. Create exam
    db_exam = models.Exam(
        name=exam.name,
        subject_id=exam.subject_id,
        max_marks=exam.max_marks,
        exam_date=exam.exam_date,
        created_by=current_user.id,
    )
    db.add(db_exam)
    db.commit()
    db.refresh(db_exam)
    return db_exam


@router.get("/exams/", response_model=list[schemas.ExamResponse])
def get_all_exams(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all exams. All authenticated users can view."""
    return db.query(models.Exam).all()


@router.get("/exams/{exam_id}", response_model=schemas.ExamResponse)
def get_exam_by_id(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return details of a single exam."""
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with ID {exam_id} not found.",
        )
    return exam


@router.put("/exams/{exam_id}", response_model=schemas.ExamResponse)
def update_exam(
    exam_id: int,
    exam_update: schemas.ExamUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Update exam details. Teacher can only update exams they created."""
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with ID {exam_id} not found.",
        )

    if current_user.role.lower() == "teacher" and db_exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update exams that you created.",
        )

    update_data = exam_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_exam, key, value)

    db.commit()
    db.refresh(db_exam)
    return db_exam


# ===========================================================================
# MARK ENDPOINTS
# ===========================================================================

@router.post("/marks/", response_model=schemas.MarkResponse, status_code=status.HTTP_201_CREATED)
def enter_mark(
    mark: schemas.MarkCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """
    Enter or update a student's marks for an exam.
    - Score must be between 0 and max_marks.
    - Teacher must be assigned to the exam's subject.
    - If a mark record already exists for this student + exam, update it instead.
    """
    # 1. Verify exam exists
    exam = db.query(models.Exam).filter(models.Exam.id == mark.exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with ID {mark.exam_id} not found.",
        )

    # 2. Validate score bounds
    if mark.score > exam.max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score ({mark.score}) cannot exceed max_marks ({exam.max_marks}) for this exam.",
        )

    # 3. Verify student exists
    student = db.query(models.Student).filter(models.Student.id == mark.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {mark.student_id} not found.",
        )

    # 4. Teachers can only enter marks for subjects assigned to them
    subject = db.query(models.Subject).filter(models.Subject.id == exam.subject_id).first()
    if current_user.role.lower() == "teacher" and subject and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not assigned to subject '{subject.subject_name}'.",
        )

    # 5. Upsert: update if exists, create if not
    existing_mark = db.query(models.Mark).filter(
        models.Mark.student_id == mark.student_id,
        models.Mark.exam_id == mark.exam_id,
    ).first()

    if existing_mark:
        # Update existing mark
        existing_mark.score = mark.score
        existing_mark.entered_by = current_user.id
        db.commit()
        db.refresh(existing_mark)
        return build_mark_response(existing_mark, exam)

    # Create new mark
    db_mark = models.Mark(
        student_id=mark.student_id,
        exam_id=mark.exam_id,
        score=mark.score,
        entered_by=current_user.id,
    )
    db.add(db_mark)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A mark record already exists for this student and exam.",
        )
    db.refresh(db_mark)
    return build_mark_response(db_mark, exam)


@router.get("/marks/student/{student_id}", response_model=list[schemas.MarkResponse])
def get_marks_for_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Return all mark records for a student.
    - Students can only view their own marks.
    - Teachers and Admins can view any student's marks.
    """
    # Verify student exists
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )

    # Student ownership check
    if current_user.role.lower() == "student":
        my_profile = db.query(models.Student).filter(
            models.Student.user_id == current_user.id
        ).first()
        if not my_profile or my_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own marks.",
            )

    marks = db.query(models.Mark).filter(models.Mark.student_id == student_id).all()

    # Build responses with grade/percentage calculated on-the-fly
    responses = []
    for m in marks:
        exam = db.query(models.Exam).filter(models.Exam.id == m.exam_id).first()
        if exam:
            responses.append(build_mark_response(m, exam))
    return responses


@router.get("/marks/{mark_id}", response_model=schemas.MarkResponse)
def get_mark_by_id(
    mark_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return a single mark record by its ID."""
    mark = db.query(models.Mark).filter(models.Mark.id == mark_id).first()
    if not mark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mark record with ID {mark_id} not found.",
        )

    # Student can only view their own record
    if current_user.role.lower() == "student":
        my_profile = db.query(models.Student).filter(
            models.Student.user_id == current_user.id
        ).first()
        if not my_profile or my_profile.id != mark.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own marks.",
            )

    exam = db.query(models.Exam).filter(models.Exam.id == mark.exam_id).first()
    return build_mark_response(mark, exam)
