from fastapi import FastAPI

app = FastAPI(title="Student Academic Tracker")

@app.get("/")
def home():
    return {"status": "success", "message": "Student Academic Tracker API is running"}