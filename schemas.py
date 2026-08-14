from pydantic import BaseModel
from datetime import date
from typing import Optional

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    username: str
    role: str = "student"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True


# --- STUDENT SCHEMAS ---
class StudentBase(BaseModel):
    full_name: str
    roll_number: str
    student_class: str
    division: str

class StudentCreate(StudentBase):
    user_id: int

class StudentResponse(StudentBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


# --- ATTENDANCE SCHEMAS ---
class AttendanceCreate(BaseModel):
    student_id: int
    subject_id: int
    date: date
    session_type: str  # "lecture" or "lab"
    status: str        # "present" or "absent"

class AttendanceResponse(AttendanceCreate):
    id: int

    class Config:
        from_attributes = True