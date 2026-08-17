from datetime import timedelta
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import auth
from database import engine, get_db
import models
import schemas

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Academic Tracker")


@app.get("/")
def home():
    return {"status": "success", "message": "Database connected & API is running!"}


# --- AUTH ENDPOINTS ---

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint. Swagger UI uses OAuth2PasswordRequestForm to automatically 
    send 'username' and 'password' as form data rather than JSON.
    """
    # 1. Fetch user from DB
    user = db.query(models.User).filter(models.User.username == form_data.username).first()

    # 2. Check if user exists and password is correct (using our hashing utility)
    if not user or not auth.verify_password(form_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Generate JWT token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


# --- USER ENDPOINTS ---

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists to prevent duplicate errors
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Hash the password BEFORE storing
    hashed_password = auth.get_password_hash(user.password)

    db_user = models.User(
        username=user.username,
        role=user.role.lower(),
        password_hash=hashed_password,  # Store the hash, never the plain text!
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/", response_model=list[schemas.UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    # PROTECTED ROUTE: Only admins can view all users
    current_user: models.User = Depends(auth.require_role(["admin"])),
):
    return db.query(models.User).all()


# --- STUDENT ENDPOINTS ---

@app.post("/students/", response_model=schemas.StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    student: schemas.StudentCreate,
    db: Session = Depends(get_db),
    # PROTECTED ROUTE: Only teachers and admins can create student records
    current_user: models.User = Depends(auth.require_role(["teacher"])),
):
    db_student = models.Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@app.get("/students/", response_model=list[schemas.StudentResponse])
def get_all_students(
    db: Session = Depends(get_db),
    # PROTECTED ROUTE: Any logged-in user can view students (student, teacher, or admin)
    current_user: models.User = Depends(auth.get_current_user),
):
    return db.query(models.Student).all()