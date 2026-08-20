"""
routers/assignments.py
Handles all Assignment and AssignmentSubmission endpoints.

Authorization rules:
  - Create / Update / Delete assignment  → Teacher or Admin only
  - List assignments                     → any logged-in user
  - Mark assignment as submitted         → the student themselves (via their own profile)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import auth
from database import get_db
import models
import schemas

router = APIRouter(prefix="/assignments", tags=["Assignments"])


# ---------------------------------------------------------------------------
# CREATE ASSIGNMENT (Teacher / Admin)
# ---------------------------------------------------------------------------

@router.post("/", response_model=schemas.AssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    assignment: schemas.AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """
    Create a new assignment for a subject.
    Only Teachers and Admins are allowed.
    Teachers can only create assignments for subjects assigned to them.
    """
    # 1. Check the subject exists
    subject = db.query(models.Subject).filter(models.Subject.id == assignment.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {assignment.subject_id} not found.",
        )

    # 2. Teachers can only create assignments for their own subjects
    if current_user.role.lower() == "teacher" and subject.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not the assigned teacher for subject '{subject.subject_name}'.",
        )

    # 3. Create and save the assignment
    db_assignment = models.Assignment(
        title=assignment.title,
        description=assignment.description,
        deadline=assignment.deadline,
        subject_id=assignment.subject_id,
        created_by=current_user.id,
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment


# ---------------------------------------------------------------------------
# GET ALL ASSIGNMENTS (any logged-in user)
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[schemas.AssignmentResponse])
def get_all_assignments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Return all assignments.
    Students automatically get assignments filtered to their class and semester subjects.
    Teachers and Admins see all assignments.
    """
    query = db.query(models.Assignment)

    if current_user.role.lower() == "student":
        # Find the student's enrolled class and semester
        student_profile = db.query(models.Student).filter(
            models.Student.user_id == current_user.id
        ).first()
        if not student_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for your account.",
            )
        # Get subject IDs for the student's class and semester
        subject_ids = [
            s.id for s in db.query(models.Subject).filter(
                models.Subject.student_class == student_profile.student_class,
                models.Subject.semester == student_profile.semester,
            ).all()
        ]
        query = query.filter(models.Assignment.subject_id.in_(subject_ids))

    return query.order_by(models.Assignment.deadline.asc()).all()


# ---------------------------------------------------------------------------
# GET ASSIGNMENTS BY SUBJECT
# ---------------------------------------------------------------------------

@router.get("/subject/{subject_id}", response_model=list[schemas.AssignmentResponse])
def get_assignments_by_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all assignments for a specific subject."""
    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found.",
        )
    return (
        db.query(models.Assignment)
        .filter(models.Assignment.subject_id == subject_id)
        .order_by(models.Assignment.deadline.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# GET A SINGLE ASSIGNMENT
# ---------------------------------------------------------------------------

@router.get("/{assignment_id}", response_model=schemas.AssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return details of a single assignment."""
    db_assignment = db.query(models.Assignment).filter(
        models.Assignment.id == assignment_id
    ).first()
    if not db_assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID {assignment_id} not found.",
        )
    return db_assignment


# ---------------------------------------------------------------------------
# UPDATE ASSIGNMENT (Teacher / Admin)
# ---------------------------------------------------------------------------

@router.put("/{assignment_id}", response_model=schemas.AssignmentResponse)
def update_assignment(
    assignment_id: int,
    assignment_update: schemas.AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Update title, description, or deadline. Only Teachers/Admins allowed."""
    db_assignment = db.query(models.Assignment).filter(
        models.Assignment.id == assignment_id
    ).first()
    if not db_assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID {assignment_id} not found.",
        )

    # Teachers can only update their own assignments
    if current_user.role.lower() == "teacher" and db_assignment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update assignments that you created.",
        )

    update_data = assignment_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_assignment, key, value)

    db.commit()
    db.refresh(db_assignment)
    return db_assignment


# ---------------------------------------------------------------------------
# DELETE ASSIGNMENT (Teacher / Admin)
# ---------------------------------------------------------------------------

@router.delete("/{assignment_id}", status_code=status.HTTP_200_OK)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["teacher", "admin"])),
):
    """Delete an assignment and all its submission records."""
    db_assignment = db.query(models.Assignment).filter(
        models.Assignment.id == assignment_id
    ).first()
    if not db_assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID {assignment_id} not found.",
        )

    if current_user.role.lower() == "teacher" and db_assignment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete assignments that you created.",
        )

    db.delete(db_assignment)
    db.commit()
    return {"message": f"Assignment '{db_assignment.title}' (ID {assignment_id}) deleted successfully."}


# ---------------------------------------------------------------------------
# SUBMIT ASSIGNMENT (Student marks their own assignment as submitted)
# ---------------------------------------------------------------------------

@router.post("/submit", response_model=schemas.SubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_assignment(
    submission: schemas.SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Allows a logged-in student to mark an assignment as submitted.
    The student can only submit for their own profile.
    """
    # 1. Ensure the caller is a student (not a teacher submitting on someone's behalf)
    if current_user.role.lower() not in ["student", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit assignments.",
        )

    # 2. Fetch the student profile of the logged-in user
    student_profile = db.query(models.Student).filter(
        models.Student.user_id == current_user.id
    ).first()
    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for your account.",
        )

    # 3. Verify the assignment exists
    assignment = db.query(models.Assignment).filter(
        models.Assignment.id == submission.assignment_id
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID {submission.assignment_id} not found.",
        )

    # 4. Check if already submitted
    existing = db.query(models.AssignmentSubmission).filter(
        models.AssignmentSubmission.assignment_id == submission.assignment_id,
        models.AssignmentSubmission.student_id == student_profile.id,
    ).first()

    if existing:
        if existing.submitted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already submitted this assignment.",
            )
        # If the record exists but wasn't submitted yet, update it
        existing.submitted = True
        existing.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    # 5. Create a new submission record
    db_submission = models.AssignmentSubmission(
        assignment_id=submission.assignment_id,
        student_id=student_profile.id,
        submitted=True,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(db_submission)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A submission record already exists for this assignment.",
        )
    db.refresh(db_submission)
    return db_submission


# ---------------------------------------------------------------------------
# GET MY SUBMISSIONS (Student views their own submissions)
# ---------------------------------------------------------------------------

@router.get("/my-submissions/list", response_model=list[schemas.SubmissionResponse])
def get_my_submissions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Returns all submission records for the logged-in student."""
    student_profile = db.query(models.Student).filter(
        models.Student.user_id == current_user.id
    ).first()
    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for your account.",
        )

    return (
        db.query(models.AssignmentSubmission)
        .filter(models.AssignmentSubmission.student_id == student_profile.id)
        .all()
    )
