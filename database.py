from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Swapped 'localhost' to '127.0.0.1' to force IPv4 connection
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:swaroop21@127.0.0.1:5432/academic_tracker_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()