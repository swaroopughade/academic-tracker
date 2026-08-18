from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


# --- AUTH SCHEMAS ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


# --- USER SCHEMAS ---
class UserBase(BaseModel):
    username: str
    role: str = "student"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- STUDENT SCHEMAS ---
class StudentBase(BaseModel):
    full_name: str
    roll_number: str
    student_class: str
    division: str
    semester: str = "1"


class StudentCreate(StudentBase):
    user_id: int


class StudentResponse(StudentBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


# --- SUBJECT SCHEMAS ---
class SubjectBase(BaseModel):
    subject_code: str = Field(..., example="CS101", description="Unique code for the subject")
    subject_name: str = Field(..., example="Data Structures", description="Name of the subject")
    student_class: str = Field(..., example="CS-A", description="Target class")
    semester: str = Field(..., example="1", description="Semester identifier")
    teacher_id: int | None = Field(None, example=2, description="User ID of assigned teacher")


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    subject_code: str | None = None
    subject_name: str | None = None
    student_class: str | None = None
    semester: str | None = None
    teacher_id: int | None = None


class SubjectResponse(SubjectBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- ATTENDANCE SCHEMAS ---
class AttendanceBase(BaseModel):
    student_id: int
    subject_id: int
    attendance_date: date = Field(default_factory=date.today)
    status: Literal["Present", "Absent", "Late"] = "Present"


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    attendance_date: date | None = None
    status: Literal["Present", "Absent", "Late"] | None = None


class AttendanceResponse(AttendanceBase):
    id: int
    marked_by: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- EXAM RESULTS / MARKS SCHEMAS ---
class ExamResultBase(BaseModel):
    student_id: int
    subject_id: int
    exam_name: str = Field(..., example="Midterm", description="Name of the exam/test")
    marks_obtained: float = Field(..., ge=0, example=85.5, description="Marks scored (non-negative)")
    maximum_marks: float = Field(..., gt=0, example=100.0, description="Total maximum marks (greater than 0)")


class ExamResultCreate(ExamResultBase):
    pass


class ExamResultUpdate(BaseModel):
    exam_name: str | None = None
    marks_obtained: float | None = Field(None, ge=0)
    maximum_marks: float | None = Field(None, gt=0)


class ExamResultResponse(ExamResultBase):
    id: int
    grade: str
    entered_by: int | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- DASHBOARD & SUMMARY SCHEMAS ---
class SubjectAttendanceSummary(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    total_classes: int
    present_classes: int
    absent_classes: int
    late_classes: int
    attendance_percentage: float


class ExamMarkItem(BaseModel):
    exam_name: str
    marks_obtained: float
    maximum_marks: float
    percentage: float
    grade: str


class SubjectMarksSummary(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    exams: list[ExamMarkItem]
    total_obtained: float
    total_maximum: float
    subject_percentage: float


class StudentDashboardResponse(BaseModel):
    student_id: int
    user_id: int
    username: str
    full_name: str
    roll_number: str
    student_class: str
    division: str
    semester: str
    subjects: list[SubjectResponse]
    attendance_summary: list[SubjectAttendanceSummary]
    marks_summary: list[SubjectMarksSummary]
    total_marks_obtained: float
    total_maximum_marks: float
    overall_percentage: float
    performance_status: str  # "Excellent", "Good", "Needs Improvement", "No Data"