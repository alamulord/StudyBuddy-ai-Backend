from fastapi import APIRouter, Depends, HTTPException
from app.schemas.settings import UserSettings
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

from datetime import datetime
from supabase import Client
from app.core.deps import get_supabase

@router.get("/", response_model=UserSettings)
def get_user_settings(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    user_id = current_user.id
    user_metadata = current_user.user_metadata or {}
    email = current_user.email
    
    # Fetch from DB
    try:
        response = supabase.table("user_settings").select("*").eq("user_id", user_id).single().execute()
        db_settings = response.data
    except Exception:
        db_settings = None
    
    if db_settings:
        preferences = db_settings.get("preferences") or {}
        
        return UserSettings(
            first_name=user_metadata.get("first_name", ""),
            last_name=user_metadata.get("last_name", ""),
            email=email,
            target_exam=db_settings.get("target_exam") or "SAT",
            coach_personality=db_settings.get("ai_personality") or "Encouraging",
            daily_goal_hours=(db_settings.get("daily_goal_minutes") or 30) / 60,
            daily_reminders=preferences.get("daily_reminders", False),
            exam_countdowns=preferences.get("exam_countdowns", True),
            streak_alerts=preferences.get("streak_alerts", True)
        )
        
    return UserSettings(
        email=email,
        first_name=user_metadata.get("first_name", ""),
        last_name=user_metadata.get("last_name", ""),
        target_exam="SAT",
        coach_personality="Encouraging",
        daily_goal_hours=0.5,
        daily_reminders=False,
        exam_countdowns=True,
        streak_alerts=True
    )

@router.put("/", response_model=UserSettings)
def update_user_settings(
    settings: UserSettings, 
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    user_id = current_user.id
    
    # Prepare data for DB
    daily_minutes = int(settings.daily_goal_hours * 60)
    preferences = {
        "daily_reminders": settings.daily_reminders,
        "exam_countdowns": settings.exam_countdowns,
        "streak_alerts": settings.streak_alerts
    }
    
    update_data = {
        "target_exam": settings.target_exam,
        "ai_personality": settings.coach_personality,
        "daily_goal_minutes": daily_minutes,
        "preferences": preferences,
        "updated_at": datetime.now().isoformat()
    }
    
    # Upsert
    # Check if exists first or just upsert (Supabase upsert needs primary key constraint)
    # user_settings primary key is user_id.
    
    # Try update first
    res = supabase.table("user_settings").update(update_data).eq("user_id", user_id).execute()
    if not res.data:
        # If no row updated, try insert (user_id is PK)
        update_data["user_id"] = user_id
        res = supabase.table("user_settings").insert(update_data).execute()
        
    return settings
