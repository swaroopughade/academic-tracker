from datetime import timedelta
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import auth
from database import engine, get_db
import models
import schemas
# Day-2 routers
from routers import subjects, attendance, marks, dashboard
# Day-3 routers
from routers import assignments, exams, alerts

from fastapi.middleware.cors import CORSMiddleware

# Automatically create every table that doesn't exist yet in PostgreSQL
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Student Academic Tracker API",
    description=(
        "Full-stack academic backend: Auth, Subjects, Attendance, "
        "Marks, Dashboard, Assignments, Exams & Smart Alerts"
    ),
    version="4.0.0",
)

# ---------------------------------------------------------------------------
# CORS MIDDLEWARE SETUP
# Allows browser frontends (e.g. Live Server on port 5500, file://, localhost)
# to make API requests without being blocked by CORS policy.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allows all origins for local development (e.g. Live Server, file://)
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allows headers like Authorization, Content-Type
)

# ---------------------------------------------------------------------------
# INCLUDE ALL ROUTERS
# ---------------------------------------------------------------------------
app.include_router(subjects.router)
app.include_router(attendance.router)
app.include_router(marks.router)           # Day-2 ExamResult marks
app.include_router(dashboard.router)
app.include_router(assignments.router)     # Day-3
app.include_router(exams.router)           # Day-3 (Exam + Mark endpoints)
app.include_router(alerts.router)          # Day-3 (combined /alerts/{student_id})


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def home():
    return {
        "status": "success",
        "message": "Student Academic Tracker API is live!",
        "version": "4.0.0",
    }


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

@app.post("/login", response_model=schemas.Token, tags=["Authentication"])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 Password Flow.
    Send username + password as form data.
    Returns a signed JWT access token valid for 60 minutes, along with user role and student profile ID (if applicable).
    """
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()

    if not user or not auth.verify_password(form_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if student profile exists for this user
    student = db.query(models.Student).filter(models.Student.user_id == user.id).first()
    student_id = student.id if student else None

    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "student_id": student_id,
    }


# ---------------------------------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------------------------------

@app.post(
    "/users/",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new user (admin / teacher / student). Password is hashed before storage."""
    existing = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user.username}' is already registered.",
        )

    db_user = models.User(
        username=user.username,
        role=user.role.lower(),
        password_hash=auth.get_password_hash(user.password),
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
    """List all users. Admin only."""
    return db.query(models.User).all()


# ---------------------------------------------------------------------------
# STUDENT PROFILE MANAGEMENT
# ---------------------------------------------------------------------------

@app.post(
    "/students/",
    response_model=schemas.StudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Students"],
)
def create_student_profile(
    student: schemas.StudentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(["admin", "teacher"])),
):
    """Create a student profile linked to an existing user account."""
    # Verify linked user exists
    user = db.query(models.User).filter(models.User.id == student.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {student.user_id} not found.",
        )
    # Only one student profile per user
    if db.query(models.Student).filter(
        models.Student.user_id == student.user_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A student profile is already linked to user ID {student.user_id}.",
        )
    # Roll number must be unique
    if db.query(models.Student).filter(
        models.Student.roll_number == student.roll_number
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roll number '{student.roll_number}' is already in use.",
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
    """List all student profiles. Accessible to all authenticated users."""
    return db.query(models.Student).all()


@app.get(
    "/students/{student_id}",
    response_model=schemas.StudentResponse,
    tags=["Students"],
)
def get_student_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch a single student profile by ID."""
    student = db.query(models.Student).filter(
        models.Student.id == student_id
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )
    return student