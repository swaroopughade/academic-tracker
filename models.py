import enum
from datetime import date
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from database import Base


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class AttendanceStatusEnum(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"


# ---------------------------------------------------------------------------
# USER MODEL
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default=RoleEnum.STUDENT, nullable=False)

    # --- Relationships ---
    student_profile   = relationship("Student",      back_populates="user",              uselist=False, cascade="all, delete-orphan")
    subjects_taught   = relationship("Subject",      back_populates="teacher")
    attendance_marked = relationship("Attendance",   back_populates="marker")
    marks_entered     = relationship("ExamResult",   back_populates="examiner")
    # Day-3 additions
    assignments_created  = relationship("Assignment",         back_populates="creator")
    exams_created        = relationship("Exam",               back_populates="creator")
    marks_created        = relationship("Mark",               back_populates="entered_by_user")


# ---------------------------------------------------------------------------
# STUDENT MODEL
# ---------------------------------------------------------------------------

class Student(Base):
    __tablename__ = "students"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name     = Column(String, nullable=False)
    roll_number   = Column(String, unique=True, index=True, nullable=False)
    student_class = Column(String, nullable=False)
    division      = Column(String, nullable=False)
    semester      = Column(String, default="1", nullable=False)

    # --- Relationships ---
    user              = relationship("User",       back_populates="student_profile")
    attendance_records= relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    exam_results      = relationship("ExamResult", back_populates="student", cascade="all, delete-orphan")
    # Day-3 additions
    submissions = relationship("AssignmentSubmission", back_populates="student", cascade="all, delete-orphan")
    marks       = relationship("Mark",                 back_populates="student",  cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# SUBJECT MODEL
# ---------------------------------------------------------------------------

class Subject(Base):
    __tablename__ = "subjects"

    id            = Column(Integer, primary_key=True, index=True)
    subject_code  = Column(String, index=True, nullable=False)
    subject_name  = Column(String, nullable=False)
    student_class = Column(String, nullable=False)
    semester      = Column(String, nullable=False)
    teacher_id    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_code", "student_class", "semester", name="uq_subject_class_semester"),
    )

    # --- Relationships ---
    teacher           = relationship("User",       back_populates="subjects_taught")
    attendance_records= relationship("Attendance", back_populates="subject", cascade="all, delete-orphan")
    exam_results      = relationship("ExamResult", back_populates="subject", cascade="all, delete-orphan")
    # Day-3 additions
    assignments = relationship("Assignment", back_populates="subject", cascade="all, delete-orphan")
    exams       = relationship("Exam",       back_populates="subject", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# ATTENDANCE MODEL (Day 2 — unchanged)
# ---------------------------------------------------------------------------

class Attendance(Base):
    __tablename__ = "attendance"

    id              = Column(Integer, primary_key=True, index=True)
    student_id      = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id      = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    attendance_date = Column(Date, default=date.today, nullable=False)
    status          = Column(String, nullable=False)   # "Present", "Absent", "Late"
    marked_by       = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "attendance_date", name="uq_student_subject_date"),
    )

    student = relationship("Student", back_populates="attendance_records")
    subject = relationship("Subject", back_populates="attendance_records")
    marker  = relationship("User",    back_populates="attendance_marked")


# ---------------------------------------------------------------------------
# EXAM RESULT MODEL (Day 2 — unchanged)
# ---------------------------------------------------------------------------

class ExamResult(Base):
    __tablename__ = "exam_results"

    id             = Column(Integer, primary_key=True, index=True)
    student_id     = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id     = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    exam_name      = Column(String, nullable=False)
    marks_obtained = Column(Float, nullable=False)
    maximum_marks  = Column(Float, nullable=False)
    grade          = Column(String, nullable=False)
    entered_by     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "exam_name", name="uq_student_subject_exam"),
    )

    student  = relationship("Student", back_populates="exam_results")
    subject  = relationship("Subject", back_populates="exam_results")
    examiner = relationship("User",    back_populates="marks_entered")


# ---------------------------------------------------------------------------
# DAY-3: ASSIGNMENT MODEL
# Teachers create assignments linked to a subject.
# ---------------------------------------------------------------------------

class Assignment(Base):
    __tablename__ = "assignments"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # When is this assignment due?
    deadline    = Column(DateTime(timezone=True), nullable=False)
    subject_id  = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    # Which teacher created it?
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    subject     = relationship("Subject", back_populates="assignments")
    creator     = relationship("User",    back_populates="assignments_created")
    # All submission records for this assignment
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# DAY-3: ASSIGNMENT SUBMISSION MODEL
# One row per student per assignment — tracks whether they submitted it.
# ---------------------------------------------------------------------------

class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id            = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id    = Column(Integer, ForeignKey("students.id",    ondelete="CASCADE"), nullable=False)
    # Has the student marked it as submitted?
    submitted     = Column(Boolean, default=False, nullable=False)
    # When did they submit? NULL if not submitted yet.
    submitted_at  = Column(DateTime(timezone=True), nullable=True)

    # Only one submission record per student per assignment
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
    )

    assignment = relationship("Assignment", back_populates="submissions")
    student    = relationship("Student",    back_populates="submissions")


# ---------------------------------------------------------------------------
# DAY-3: EXAM MODEL
# Separate from ExamResult — an Exam is the "event"; Marks link students to it.
# ---------------------------------------------------------------------------

class Exam(Base):
    __tablename__ = "exams"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)            # e.g. "Midterm 2026"
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    max_marks  = Column(Float, nullable=False)
    exam_date  = Column(Date, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Each exam name must be unique within a subject
    __table_args__ = (
        UniqueConstraint("name", "subject_id", name="uq_exam_name_subject"),
    )

    subject  = relationship("Subject", back_populates="exams")
    creator  = relationship("User",    back_populates="exams_created")
    # All marks recorded for this exam
    marks    = relationship("Mark", back_populates="exam", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# DAY-3: MARK MODEL
# Links a specific student to a specific exam and stores their score.
# ---------------------------------------------------------------------------

class Mark(Base):
    __tablename__ = "marks"

    id            = Column(Integer, primary_key=True, index=True)
    student_id    = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    exam_id       = Column(Integer, ForeignKey("exams.id",    ondelete="CASCADE"), nullable=False)
    score         = Column(Float, nullable=False)   # actual marks scored
    entered_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # One score record per student per exam
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_student_exam"),
    )

    student        = relationship("Student", back_populates="marks")
    exam           = relationship("Exam",    back_populates="marks")
    entered_by_user= relationship("User",   back_populates="marks_created")