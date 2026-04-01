from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)
print("DEBUG: main.py has been loaded/reloaded!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Be specific about allowed origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly include OPTIONS
    allow_headers=["*"],  # Allows all headers including Authorization
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/debug-ping")
def debug_ping():
    return {"status": "alive", "message": "Reload successful!"}

@app.get("/")
def read_root():
    return {"message": "Welcome to StudyBuddy API"}
