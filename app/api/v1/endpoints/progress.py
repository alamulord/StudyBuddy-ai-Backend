from fastapi import APIRouter, Depends
from typing import Annotated, Any, Dict, List
from app.core.deps import get_current_user, get_supabase
from app.schemas.progress import ProgressData, ReadinessPoint, ActivityPoint, TopicMastery, UpcomingItem, ActiveTask
from supabase import Client
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/", response_model=ProgressData)
def get_progress_data(
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Get user progress data.
    Aggregates data from materials and user_settings to visualize progress.
    """
    
    # 1. Weekly Activity (Simulated from materials for now)
    activity_data = [
        ActivityPoint(day="Mon", hours=0),
        ActivityPoint(day="Tue", hours=0),
        ActivityPoint(day="Wed", hours=0),
        ActivityPoint(day="Thu", hours=0),
        ActivityPoint(day="Fri", hours=0),
        ActivityPoint(day="Sat", hours=0),
        ActivityPoint(day="Sun", hours=0),
    ]
    
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    materials_res = supabase.table("materials").select("created_at").eq("user_id", current_user.id).gte("created_at", seven_days_ago.isoformat()).execute()
    
    if materials_res.data:
        for m in materials_res.data:
            dt = datetime.fromisoformat(m['created_at'].replace('Z', '+00:00'))
            day_idx = dt.weekday() # Mon=0, Sun=6
            activity_data[day_idx].hours += 0.5 # Assume 30 mins per upload
            
    # 2. Readiness History
    count_res = supabase.table("materials").select("id", count="exact").eq("user_id", current_user.id).execute()
    total_mats = count_res.count if count_res.count else 0
    current_readiness = min(10 + (total_mats * 5), 95)
    
    readiness_history = [
        ReadinessPoint(name="Wk 1", score=max(current_readiness - 15, 10)),
        ReadinessPoint(name="Wk 2", score=max(current_readiness - 10, 15)),
        ReadinessPoint(name="Wk 3", score=max(current_readiness - 5, 20)),
        ReadinessPoint(name="Current", score=current_readiness),
    ]

    # 3. Topic Mastery
    subjects_res = supabase.table("materials").select("subject").eq("user_id", current_user.id).execute()
    subject_counts: Dict[str, int] = {}
    if subjects_res.data:
        for item in subjects_res.data:
            s = item.get('subject', 'General')
            subject_counts[s] = subject_counts.get(s, 0) + 1
            
    topic_mastery = []
    colors = ["emerald-500", "blue-500", "amber-500", "purple-500"]
    
    for i, (subj, count) in enumerate(subject_counts.items()):
        if i >= 4: break
        score = min(count * 10, 100)
        topic_mastery.append(TopicMastery(
            topic=subj,
            subtext=f"{count} materials processed",
            score=score,
            color=colors[i % len(colors)]
        ))
        
    if not topic_mastery:
        topic_mastery.append(TopicMastery(topic="No Data", subtext="Upload to see mastery", score=0, color="gray-400"))

    # 4. Upcoming
    upcoming = [
        UpcomingItem(
            title="Tomorrow",
            time="Tomorrow",
            subtitle="Daily Review",
            meta="20 mins • Medium Priority",
            priority="high"
        )
    ]

    # 5. Active Tasks
    active_tasks = []
    processing_res = supabase.table("materials").select("id", "title", "processing_step", "processing_percentage").eq("user_id", current_user.id).eq("status", "processing").execute()
    
    if processing_res.data:
        for t in processing_res.data:
            active_tasks.append(ActiveTask(
                id=str(t['id']),
                title=t['title'],
                step=t.get('processing_step', 'Processing...'),
                percentage=t.get('processing_percentage', 0)
            ))

    return ProgressData(
        readiness_history=readiness_history,
        weekly_activity=activity_data,
        topic_mastery=topic_mastery,
        upcoming=upcoming,
        active_tasks=active_tasks,
        streak=1 if total_mats > 0 else 0,
        total_hours=sum(a.hours for a in activity_data)
    )
