from pydantic import BaseModel
from typing import List, Optional

class UserStats(BaseModel):
    exam_readiness: int
    readiness_trend: int
    current_streak: int
    best_streak: int
    mastery_score: str
    mastery_trend: int

class FocusItem(BaseModel):
    title: str
    color: str

class FocusArea(BaseModel):
    title: str
    description: str
    weak_concepts: List[str]
    items: List[FocusItem]

class RecentMaterial(BaseModel):
    id: str
    title: str
    subject: str
    type: str # 'PDF Note', 'Practice Quiz', 'Video Lecture'
    last_opened: str
    progress: int
    status: str # 'Done', 'In Progress'

class DashboardData(BaseModel):
    user_stats: UserStats
    focus_area: FocusArea
    recent_materials: List[RecentMaterial]
