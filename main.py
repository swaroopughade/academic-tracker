from datetime import timedelta
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import auth
from database import engine, get_db
import models
import schemas
from routers import subjects, attendance, marks, dashboard

# Create all database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Student Academic Tracker API",
    description="Backend API for Student Academic Tracking (Auth, Subjects, Attendance, Marks & Dashboard)",
    version="2.0.0",
)

# --- INCLUDE ROUTERS ---
app.include_router(subjects.router)
app.include_router(attendance.router)
app.include_router(marks.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"])
def home():
    return {
        "status": "success",
        "message": "Student Academic Tracker API is live and operational!",
        "version": "2.0.0"
    }


# --- AUTHENTICATION ENDPOINTS ---

@app.post("/login", response_model=schemas.Token, tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 Password Flow Login.
    Accepts form data containing 'username' and 'password', verifies credentials,
    and returns a signed JWT access token.
    """
    user = db.query(models.User).filter(models.User.username == form_data.username).first()

    if not user or not auth.verify_password(form_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


# --- USER MANAGEMENT ENDPOINTS ---

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED, tags=["Users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account with hashed password.
    Roles: admin, teacher, student
    """
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user.username}' is already registered."
        )

    # Hash the password BEFORE persisting
    hashed_password = auth.get_password_hash(user.password)

    db_user = models.User(
        username=user.username,
        role=user.role.lower(),
        password_hash=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/", response_model=list[schemas.UserResponse], tags=["Users"])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["admin"])),
):
    """List all registered users. Restricted to Admins."""
    return db.query(models.User).all()


# --- STUDENT PROFILE ENDPOINTS ---

@app.post("/students/", response_model=schemas.StudentResponse, status_code=status.HTTP_201_CREATED, tags=["Students"])
def create_student_profile(
    student: schemas.StudentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["admin", "teacher"])),
):
    """
    Create a student profile linked to an existing user account.
    Restricted to Admins and Teachers.
    """
    # 1. Verify user exists
    user = db.query(models.User).filter(models.User.id == student.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {student.user_id} not found."
        )

    # 2. Check if student profile already linked to this user
    existing_link = db.query(models.Student).filter(models.Student.user_id == student.user_id).first()
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A student profile is already linked to user ID {student.user_id}."
        )

    # 3. Check for unique roll number
    existing_roll = db.query(models.Student).filter(models.Student.roll_number == student.roll_number).first()
    if existing_roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roll number '{student.roll_number}' is already assigned to another student."
        )

    db_student = models.Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@app.get("/students/", response_model=list[schemas.StudentResponse], tags=["Students"])
def get_all_students(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """List all students. Accessible to all authenticated users."""
    return db.query(models.Student).all()


@app.get("/students/{student_id}", response_model=schemas.StudentResponse, tags=["Students"])
def get_student_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch single student profile by ID."""
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )
    return student