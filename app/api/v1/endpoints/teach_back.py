from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.services.teach_back import evaluate_teach_back
from pydantic import BaseModel
from typing import Any

router = APIRouter()

class TeachBackSubmit(BaseModel):
    material_id: str
    topic: str
    explanation: str

@router.post("/evaluate")
async def evaluate(
    data: TeachBackSubmit,
    current_user: Any = Depends(get_current_user)
):
    try:
        result = await evaluate_teach_back(
            user_id=current_user.id,
            material_id=data.material_id,
            topic=data.topic,
            explanation=data.explanation
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
