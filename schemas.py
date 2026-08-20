from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# AUTH SCHEMAS
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


# ---------------------------------------------------------------------------
# USER SCHEMAS
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    username: str
    role: str = "student"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# STUDENT SCHEMAS
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SUBJECT SCHEMAS
# ---------------------------------------------------------------------------

class SubjectBase(BaseModel):
    subject_code: str  = Field(..., example="CS101")
    subject_name: str  = Field(..., example="Data Structures")
    student_class: str = Field(..., example="CS-A")
    semester: str      = Field(..., example="1")
    teacher_id: int | None = Field(None, example=2)


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    subject_code: str | None  = None
    subject_name: str | None  = None
    student_class: str | None = None
    semester: str | None      = None
    teacher_id: int | None    = None


class SubjectResponse(SubjectBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# ATTENDANCE SCHEMAS
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DAY-2 EXAM RESULT SCHEMAS (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ExamResultBase(BaseModel):
    student_id: int
    subject_id: int
    exam_name: str  = Field(..., example="Midterm")
    marks_obtained: float = Field(..., ge=0, example=85.5)
    maximum_marks: float  = Field(..., gt=0, example=100.0)


class ExamResultCreate(ExamResultBase):
    pass


class ExamResultUpdate(BaseModel):
    exam_name: str | None      = None
    marks_obtained: float | None = Field(None, ge=0)
    maximum_marks: float | None  = Field(None, gt=0)


class ExamResultResponse(ExamResultBase):
    id: int
    grade: str
    entered_by: int | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DASHBOARD & SUMMARY SCHEMAS
# ---------------------------------------------------------------------------

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
    performance_status: str


# ---------------------------------------------------------------------------
# DAY-3: ASSIGNMENT SCHEMAS
# ---------------------------------------------------------------------------

class AssignmentBase(BaseModel):
    title: str       = Field(..., example="Binary Trees Lab Report")
    description: str | None = Field(None, example="Write a report on BST operations")
    deadline: datetime = Field(..., example="2026-08-25T23:59:00")
    subject_id: int  = Field(..., example=1)


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    title: str | None       = None
    description: str | None = None
    deadline: datetime | None = None
    subject_id: int | None  = None


class AssignmentResponse(AssignmentBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DAY-3: ASSIGNMENT SUBMISSION SCHEMAS
# ---------------------------------------------------------------------------

class SubmissionCreate(BaseModel):
    """A student uses this to mark their assignment as submitted."""
    assignment_id: int = Field(..., example=1)


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    submitted: bool
    submitted_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DAY-3: EXAM SCHEMAS (new Exam model — separate from ExamResult)
# ---------------------------------------------------------------------------

class ExamBase(BaseModel):
    name: str       = Field(..., example="Midterm 2026")
    subject_id: int = Field(..., example=1)
    max_marks: float = Field(..., gt=0, example=100.0)
    exam_date: date = Field(..., example="2026-08-30")


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    name: str | None      = None
    max_marks: float | None = Field(None, gt=0)
    exam_date: date | None = None


class ExamResponse(ExamBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DAY-3: MARK SCHEMAS (score for a student in a specific Exam)
# ---------------------------------------------------------------------------

class MarkCreate(BaseModel):
    student_id: int = Field(..., example=1)
    exam_id: int    = Field(..., example=1)
    score: float    = Field(..., ge=0, example=78.5)


class MarkUpdate(BaseModel):
    score: float = Field(..., ge=0, example=82.0)


class MarkResponse(BaseModel):
    id: int
    student_id: int
    exam_id: int
    score: float
    # Grade is calculated on-the-fly from score / exam.max_marks, not stored
    grade: str
    percentage: float
    entered_by: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# DAY-3: SMART ALERTS SCHEMA
# One endpoint returns all three alert types combined.
# ---------------------------------------------------------------------------

class AlertItem(BaseModel):
    alert_type: str    # "attendance_shortage", "deadline_reminder", "performance_warning"
    message: str


class StudentAlertsResponse(BaseModel):
    student_id: int
    full_name: str
    alerts: list[AlertItem]