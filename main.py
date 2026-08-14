from fastapi import FastAPI
import models
from database import engine

# Automatically create all tables in PostgreSQL
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Academic Tracker")

@app.get("/")
def home():
    return {"status": "success", "message": "Database connected & API is running!"}