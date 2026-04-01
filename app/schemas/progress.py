from pydantic import BaseModel
from typing import List

class ReadinessPoint(BaseModel):
    name: str  # e.g., "Wk 1", "Current"
    score: int

class ActivityPoint(BaseModel):
    day: str   # e.g., "Mon"
    hours: float

class TopicMastery(BaseModel):
    topic: str
    subtext: str
    score: int
    color: str # hex or tailwind class suffix? let's stick to hex for chart compatibility or class names

class UpcomingItem(BaseModel):
    title: str
    time: str # e.g. "Tomorrow" or date
    subtitle: str # e.g. "Statistics Quiz Prep"
    meta: str # e.g. "30 mins • Medium Intensity"
    priority: str # "high", "medium", "low"

class ActiveTask(BaseModel):
    id: str
    title: str
    step: str
    percentage: int

class ProgressData(BaseModel):
    readiness_history: List[ReadinessPoint]
    weekly_activity: List[ActivityPoint]
    topic_mastery: List[TopicMastery]
    upcoming: List[UpcomingItem]
    active_tasks: List[ActiveTask]
    streak: int
    total_hours: float
