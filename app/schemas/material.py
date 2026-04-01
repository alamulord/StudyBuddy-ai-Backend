from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class MaterialBase(BaseModel):
    title: str
    subject: Optional[str] = None
    type: str  # 'PDF', 'Video', 'Text', 'Quiz'
    summary: Optional[str] = None

class MaterialCreate(MaterialBase):
    pass

class Material(MaterialBase):
    id: UUID
    user_id: UUID
    storage_path: Optional[str] = None
    transcription: Optional[str] = None
    status: str
    processing_step: Optional[str] = None
    processing_percentage: Optional[int] = 0
    created_at: datetime
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True
