from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FlashcardBase(BaseModel):
    front: str
    back: str
    material_id: str

class FlashcardCreate(FlashcardBase):
    pass

class Flashcard(FlashcardBase):
    id: str
    created_at: datetime
    # SM-2 Spaced Repetition fields
    next_review: Optional[datetime] = None
    interval: Optional[float] = 0.0
    repetition: Optional[int] = 0
    easiness_factor: Optional[float] = 2.5
    
    class Config:
        from_attributes = True
