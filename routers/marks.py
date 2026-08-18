from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import auth
from database import get_db
import models
import schemas

router = APIRouter(prefix="/marks", tags=["Marks & Exam Results"])


# --- GRADE CALCULATION HELPER ---
def calculate_grade(marks_obtained: float, maximum_marks: float) -> str:
    """Calculate letter grade based on percentage scored."""
    if maximum_marks <= 0:
        return "N/A"
    percentage = (marks_obtained / maximum_marks) * 100.0
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 50:
        return "D"
    return "F"


# --- ENTER MARKS (Teacher & Admin) ---
@router.post("/", response_model=schemas.ExamResultResponse, status_code=status.HTTP_201_CREATED)
def enter_marks(
    result: schemas.ExamResultCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """
    Enter exam marks for a student.
    - Teachers can only enter marks for their assigned subjects.
    - Admins can enter marks for any subject.
    - Validates marks range (0 <= marks_obtained <= maximum_marks).
    - Automatically calculates grade.
    - Prevents duplicate marks for the same student, subject, and exam name.
    """
    # 1. Validate marks bounds
    if result.marks_obtained > result.maximum_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks obtained ({result.marks_obtained}) cannot exceed maximum marks ({result.maximum_marks})."
        )

    # 2. Validate student exists
    student = db.query(models.Student).filter(models.Student.id == result.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {result.student_id} not found."
        )

    # 3. Validate subject exists
    subject = db.query(models.Subject).filter(models.Subject.id == result.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {result.subject_id} not found."
        )

    # 4. If teacher, verify subject assignment
    if current_user.role.lower() == "teacher" and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You are not assigned to subject '{subject.subject_name}'."
        )

    # 5. Check for duplicate exam result
    existing = db.query(models.ExamResult).filter(
        models.ExamResult.student_id == result.student_id,
        models.ExamResult.subject_id == result.subject_id,
        models.ExamResult.exam_name.ilike(result.exam_name.strip()),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exam result for '{result.exam_name}' already exists for Student ID {result.student_id} and Subject ID {result.subject_id}."
        )

    # 6. Calculate grade and save
    computed_grade = calculate_grade(result.marks_obtained, result.maximum_marks)

    db_result = models.ExamResult(
        student_id=result.student_id,
        subject_id=result.subject_id,
        exam_name=result.exam_name.strip(),
        marks_obtained=result.marks_obtained,
        maximum_marks=result.maximum_marks,
        grade=computed_grade,
        entered_by=current_user.id,
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


# --- GET SINGLE MARK RECORD BY ID ---
@router.get("/{mark_id}", response_model=schemas.ExamResultResponse)
def get_mark_by_id(
    mark_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get a single mark record by ID.
    - Students can only view their own mark records.
    - Teachers and Admins can view any record.
    """
    record = db.query(models.ExamResult).filter(models.ExamResult.id == mark_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam result record with ID {mark_id} not found."
        )

    # Student ownership check
    if current_user.role.lower() == "student":
        student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student_profile or record.student_id != student_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own exam results."
            )

    return record


# --- GET ALL MARKS FOR A STUDENT ---
@router.get("/student/{student_id}", response_model=list[schemas.ExamResultResponse])
def get_marks_for_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get all exam marks for a specific student.
    - Students can only view their own marks.
    - Teachers and Admins can view marks for any student.
    """
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )

    if current_user.role.lower() == "student":
        student_profile = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student_profile or student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own marks."
            )

    records = db.query(models.ExamResult).filter(models.ExamResult.student_id == student_id).all()
    return records


# --- UPDATE MARKS (Teacher & Admin) ---
@router.put("/{mark_id}", response_model=schemas.ExamResultResponse)
def update_marks(
    mark_id: int,
    mark_update: schemas.ExamResultUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Update exam marks and re-calculate grade automatically."""
    db_result = db.query(models.ExamResult).filter(models.ExamResult.id == mark_id).first()
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam result record with ID {mark_id} not found."
        )

    # Teacher assignment check
    subject = db.query(models.Subject).filter(models.Subject.id == db_result.subject_id).first()
    if current_user.role.lower() == "teacher" and subject and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not assigned to this subject."
        )

    update_data = mark_update.model_dump(exclude_unset=True)

    new_obtained = update_data.get("marks_obtained", db_result.marks_obtained)
    new_max = update_data.get("maximum_marks", db_result.maximum_marks)

    if new_obtained > new_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks obtained ({new_obtained}) cannot exceed maximum marks ({new_max})."
        )

    # Update values
    for key, value in update_data.items():
        if key == "exam_name" and value is not None:
            setattr(db_result, key, value.strip())
        else:
            setattr(db_result, key, value)

    # Re-calculate grade
    db_result.grade = calculate_grade(db_result.marks_obtained, db_result.maximum_marks)
    db_result.entered_by = current_user.id

    try:
        db.commit()
        db.refresh(db_result)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate exam result exists with the updated exam name."
        )

    return db_result


# --- DELETE MARKS (Teacher & Admin) ---
@router.delete("/{mark_id}", status_code=status.HTTP_200_OK)
def delete_marks(
    mark_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Delete an exam result record."""
    db_result = db.query(models.ExamResult).filter(models.ExamResult.id == mark_id).first()
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam result record with ID {mark_id} not found."
        )

    subject = db.query(models.Subject).filter(models.Subject.id == db_result.subject_id).first()
    if current_user.role.lower() == "teacher" and subject and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not assigned to this subject."
        )

    db.delete(db_result)
    db.commit()
    return {"message": f"Exam result record ID {mark_id} successfully deleted."}
