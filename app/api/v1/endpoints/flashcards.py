from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Any, List
from app.core.deps import get_current_user, get_supabase
from app.schemas.flashcard import Flashcard
from supabase import Client

router = APIRouter()

@router.get("/{material_id}", response_model=List[Flashcard])
def get_flashcards(
    material_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Get all flashcards for a specific material.
    """
    try:
        # Verify material permission
        material_res = supabase.table("materials").select("id").eq("id", material_id).eq("user_id", current_user.id).single().execute()
        if not material_res.data:
             raise HTTPException(status_code=404, detail="Material not found or access denied")
        
        # Fetch flashcards
        result = supabase.table("flashcards").select("*").eq("material_id", material_id).execute()
        return result.data
    except Exception as e:
        print(f"Error fetching flashcards: {e}")
        # In a real app we might want to return 500, but for now empty list or specific error is fine
        # If the table doesn't exist, it will throw.
        raise HTTPException(status_code=500, detail=str(e))
@router.put("/update/{flashcard_id}")
def update_flashcard(
    flashcard_id: str,
    data: dict,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
):
    try:
        # Verify ownership via join or direct check if flashcard belongs to user's material
        # Simplest: check if flashcard exists and its material belongs to user
        flashcard_res = supabase.table("flashcards").select("material_id").eq("id", flashcard_id).single().execute()
        if not flashcard_res.data:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        
        material_id = flashcard_res.data["material_id"]
        material_res = supabase.table("materials").select("id").eq("id", material_id).eq("user_id", current_user.id).single().execute()
        if not material_res.data:
            raise HTTPException(status_code=403, detail="Access denied")
            
        update_data = {
            "front": data.get("front"),
            "back": data.get("back")
        }
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = supabase.table("flashcards").update(update_data).eq("id", flashcard_id).execute()
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
