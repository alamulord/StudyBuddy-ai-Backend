from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, get_supabase
from app.services.ai.llm_client import generate_content
from pydantic import BaseModel
from typing import List, Optional, Any
from supabase import Client
from datetime import datetime

router = APIRouter()

class ChatMessage(BaseModel):
    role: str # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    material_id: str
    message: str
    history: Optional[List[ChatMessage]] = []

@router.post("/")
async def chat_with_tutor(
    request: ChatRequest,
    current_user: Any = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        # 1. Fetch material context
        material_res = supabase.table("materials").select("title, summary, transcription").eq("id", request.material_id).execute()
        if not material_res.data:
            raise HTTPException(status_code=404, detail="Material not found")
        
        material = material_res.data[0]
        context = material.get("transcription") or material.get("summary") or "No content available."
        title = material.get("title", "this material")

        # 2. Construct System Prompt
        system_prompt = f"""
        You are a helpful and expert AI Tutor for the application "StudyBuddy".
        Your goal is to help the student understand the following study material: "{title}".
        
        REFERENCE MATERIAL CONTEXT:
        {context}
        
        GUIDELINES:
        1. Base your answers strictly on the provided context.
        2. If the user asks something outside the scope of the material, politely steer them back.
        3. Be encouraging, concise, and pedagogical.
        4. Use Markdown for formatting.
        """

        # 3. Prepare AI Input
        # For simplicity, we'll append history if provided
        ai_input = [system_prompt]
        if request.history:
            for msg in request.history:
                ai_input.append(f"{msg.role.upper()}: {msg.content}")
        
        ai_input.append(f"USER: {request.message}")

        # 4. Generate Response
        response = await generate_content(ai_input, model_name="gemini-1.5-flash")
        
        return {
            "response": response,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
