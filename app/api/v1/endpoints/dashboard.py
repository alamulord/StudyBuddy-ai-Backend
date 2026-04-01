from fastapi import APIRouter, Depends
from typing import Annotated, Any
from app.core.deps import get_current_user, get_supabase
from app.schemas.dashboard import DashboardData, UserStats, FocusArea, FocusItem, RecentMaterial
from supabase import Client
from datetime import datetime

router = APIRouter()

def format_relative_time(date_str: str) -> str:
    try:
        # Simple parser for Supabase ISO string, improving robustness would be good later
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        delta = datetime.now(dt.tzinfo) - dt
        
        if delta.days > 0:
            return f"{delta.days} days ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes} mins ago"
        return "Just now"
    except Exception:
        return "Recently"

@router.get("/stats", response_model=DashboardData)
def get_dashboard_stats(
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Get current user dashboard statistics fetching real data from DB.
    Handles empty states (zero data) if no usage.
    """
    
    # 1. Fetch Recent Materials
    materials_res = supabase.table("materials").select("*").eq("user_id", current_user.id).order("created_at", desc=True).limit(5).execute()
    materials_data = materials_res.data if materials_res.data else []
    
    recent_materials = []
    subjects = set()
    
    for m in materials_data:
        # Collect subjects for Focus Area logic
        if m.get("subject"):
            subjects.add(m["subject"])
            
        recent_materials.append(RecentMaterial(
            id=str(m["id"]),
            title=m.get("title", "Untitled"),
            subject=m.get("subject", "General"),
            type=m.get("type", "PDF"), 
            last_opened=format_relative_time(m.get("created_at")),
            progress=m.get("progress", 0), 
            status=m.get("status", "In Progress").title()
        ))

    # 2. Calculate Stats based on REAL usage
    
    # Fetch detailed stats for aggregating
    stats_res = supabase.table("materials").select("status", "processing_percentage", "subject", "last_study_session", "study_sessions_count").eq("user_id", current_user.id).execute()
    all_materials = stats_res.data if stats_res.data else []
    
    total_materials = len(all_materials)
    ready_count = sum(1 for m in all_materials if m.get("status") == "ready")
    
    # Calculate Readiness: Average of processing completeness + study sessions bonus
    if total_materials > 0:
        avg_processing = sum(m.get("processing_percentage", 0) for m in all_materials) / total_materials
        total_sessions = sum(m.get("study_sessions_count", 0) for m in all_materials)
        
        base_score = avg_processing * 0.6  # Weight processing as 60% of readiness base
        study_bonus = min(total_sessions * 5, 40) # Weight actual study sessions as 40%
        readiness = int(min(base_score + study_bonus, 100))
    else:
        readiness = 0
        
    max_depth = max([m.get("study_sessions_count", 0) for m in all_materials]) if all_materials else 0
    current_streak = min(max_depth, 365) # Simple proxy
        
    user_stats = UserStats(
        exam_readiness=readiness,
        readiness_trend=5, # Placeholder
        current_streak=current_streak, 
        best_streak=max(current_streak, 5),
        mastery_score="A-" if readiness > 80 else ("B+" if readiness > 60 else "C"),
        mastery_trend=2
    )
    
    # Determine Focus Area
    subject_counts = {}
    for m in all_materials:
        sub = m.get("subject", "General")
        subject_counts[sub] = subject_counts.get(sub, 0) + 1
        
    primary_subject = max(subject_counts, key=subject_counts.get) if subject_counts else "General Studies"
    
    focus_area = FocusArea(
        title=f"Master {primary_subject}",
        description=f"You have {subject_counts.get(primary_subject, 0)} items in this subject. Keep pushing!",
        weak_concepts=[f"{primary_subject} Deep Dive"],
        items=[
            FocusItem(title=f"Review {primary_subject}", color="indigo-400"),
            FocusItem(title="Take a Quiz", color="emerald-400"),
        ]
    )

    return DashboardData(
        user_stats=user_stats,
        focus_area=focus_area,
        recent_materials=recent_materials
    )
