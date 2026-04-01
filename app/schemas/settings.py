from pydantic import BaseModel, EmailStr
from typing import Optional

class UserSettingsBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    
    # Study Preferences
    target_exam: Optional[str] = "SAT (Scholastic Assessment Test)"
    coach_personality: Optional[str] = "Encouraging"
    daily_goal_hours: Optional[float] = 2.5
    
    # Notifications
    daily_reminders: Optional[bool] = False
    exam_countdowns: Optional[bool] = True
    streak_alerts: Optional[bool] = True

class UserSettings(UserSettingsBase):
    pass
