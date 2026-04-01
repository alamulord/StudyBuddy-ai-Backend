from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict
from app.core.deps import get_current_user
from app.services.quiz import generate_quiz_for_material, submit_quiz_attempt
from app.core.deps import get_supabase
from pydantic import BaseModel
from supabase import AuthApiError

router = APIRouter()

class QuizCreate(BaseModel):
    material_id: str
    difficulty: str = "standard"
    num_questions: int = 10

class QuizSubmit(BaseModel):
    answers: Dict[str, str] # {question_id: selected_answer}
    time_taken: int # in seconds

@router.post("/generate")
async def create_quiz(
    data: QuizCreate,
    current_user = Depends(get_current_user)
):
    try:
        # For now we do it synchronously since it's relatively fast with Flash
        # but in production you'd use a background task and polling.
        # However, to keep it simple and match the current Material processing flow:
        quiz_id = await generate_quiz_for_material(
            user_id=current_user.id,
            material_id=data.material_id,
            difficulty=data.difficulty,
            num_questions=data.num_questions
        )
        return {"quiz_id": quiz_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    current_user = Depends(get_current_user)
):
    supabase = get_supabase()
    
    # Verify ownership
    quiz_res = supabase.table("quizzes").select("*").eq("id", quiz_id).eq("user_id", current_user.id).execute()
    if not quiz_res.data:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    questions_res = supabase.table("quiz_questions").select("*").eq("quiz_id", quiz_id).execute()
    
    return {
        "quiz": quiz_res.data[0],
        "questions": questions_res.data
    }

@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    submission: QuizSubmit,
    current_user = Depends(get_current_user)
):
    try:
        result = await submit_quiz_attempt(
            user_id=current_user.id,
            quiz_id=quiz_id,
            answers=submission.answers,
            time_taken=submission.time_taken
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/attempts/recent")
async def get_recent_attempts(
    current_user = Depends(get_current_user),
    limit: int = 5
):
    supabase = get_supabase()
    res = supabase.table("quiz_attempts")\
        .select("*, quizzes(title)")\
        .eq("user_id", current_user.id)\
        .order("completed_at", desc=True)\
        .limit(limit)\
        .execute()
    return res.data
