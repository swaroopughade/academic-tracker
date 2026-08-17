import os
from datetime import datetime, timedelta, timezone
import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

# Load environment variables from the .env file
load_dotenv()

# JWT Configuration
SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback_secret_key_for_development")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

# OAuth2 scheme configures Swagger UI to know where to send the login request (to the "/login" endpoint)
# This enables the "Authorize" button in the docs!
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- HASHING UTILITIES ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if the provided plain password matches the hashed password in the DB."""
    # bcrypt requires bytes, so encode strings to utf-8
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Convert a plain text password into a secure bcrypt hash."""
    # Generate salt and hash the password
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


# --- JWT UTILITIES ---

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate a JWT token with an expiration time."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    # Sign the token using our secret key
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- DEPENDENCIES ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """
    Dependency that extracts the token from the Bearer header, decodes it,
    verifies it, and returns the corresponding User object from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode the token using our secret key and algorithm
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        # Validate that the token format is correct
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # Fetch the user from the database
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception

    return user


def require_role(required_roles: str | list[str]):
    """
    Dependency generator that checks if the current user has the required role.
    Accepts either a single string (e.g., "teacher") or a list of strings (e.g., ["teacher", "admin"]).
    Admins are always allowed access by default.
    """
    # Normalize required_roles to a list of lowercase strings
    if isinstance(required_roles, str):
        allowed_roles = [required_roles.lower()]
    else:
        allowed_roles = [r.lower() for r in required_roles]

    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        user_role = str(current_user.role).lower()
        if user_role not in allowed_roles and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker
