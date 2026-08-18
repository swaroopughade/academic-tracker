import enum
from datetime import date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Date,
    DateTime,
    UniqueConstraint,
    func
)
from sqlalchemy.orm import relationship
from database import Base


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class AttendanceStatusEnum(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"


# --- USER MODEL ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default=RoleEnum.STUDENT, nullable=False)

    # Relationships
    student_profile = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    subjects_taught = relationship("Subject", back_populates="teacher")
    attendance_marked = relationship("Attendance", back_populates="marker")
    marks_entered = relationship("ExamResult", back_populates="examiner")


# --- STUDENT MODEL ---
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    roll_number = Column(String, unique=True, index=True, nullable=False)
    student_class = Column(String, nullable=False)
    division = Column(String, nullable=False)
    semester = Column(String, default="1", nullable=False)

    # Relationships
    user = relationship("User", back_populates="student_profile")
    attendance_records = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    exam_results = relationship("ExamResult", back_populates="student", cascade="all, delete-orphan")


# --- SUBJECT MODEL ---
class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    subject_code = Column(String, index=True, nullable=False)
    subject_name = Column(String, nullable=False)
    student_class = Column(String, nullable=False)  # e.g., "10th", "FYBSc", "CS-A"
    semester = Column(String, nullable=False)       # e.g., "1", "Sem-1"
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Prevent duplicate subject code for the same class and semester
    __table_args__ = (
        UniqueConstraint("subject_code", "student_class", "semester", name="uq_subject_class_semester"),
    )

    # Relationships
    teacher = relationship("User", back_populates="subjects_taught")
    attendance_records = relationship("Attendance", back_populates="subject", cascade="all, delete-orphan")
    exam_results = relationship("ExamResult", back_populates="subject", cascade="all, delete-orphan")


# --- ATTENDANCE MODEL ---
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    attendance_date = Column(Date, default=date.today, nullable=False)
    status = Column(String, nullable=False)  # "Present", "Absent", "Late"
    marked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Prevent duplicate attendance for the same student, subject, and date
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "attendance_date", name="uq_student_subject_date"),
    )

    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    subject = relationship("Subject", back_populates="attendance_records")
    marker = relationship("User", back_populates="attendance_marked")


# --- EXAM RESULT (MARKS) MODEL ---
class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    exam_name = Column(String, nullable=False)  # e.g., "Midterm", "Final Exam", "Unit Test 1"
    marks_obtained = Column(Float, nullable=False)
    maximum_marks = Column(Float, nullable=False)
    grade = Column(String, nullable=False)      # e.g., "A+", "A", "B", "C", "D", "F"
    entered_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Prevent duplicate results for the same student, subject, and exam name
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "exam_name", name="uq_student_subject_exam"),
    )

    # Relationships
    student = relationship("Student", back_populates="exam_results")
    subject = relationship("Subject", back_populates="exam_results")
    examiner = relationship("User", back_populates="marks_entered")