from fastapi import APIRouter
from app.api.v1.endpoints import auth, dashboard, materials, settings, flashcards, progress, quizzes, teach_back, chat, admin

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(flashcards.router, prefix="/flashcards", tags=["flashcards"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(teach_back.router, prefix="/teach-back", tags=["teach-back"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

