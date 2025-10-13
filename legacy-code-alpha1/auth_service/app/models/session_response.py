"""
Session response models for Auth Service
"""
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Response model for session data"""
    user_id: str
    email: str
    role: Literal['student', 'teacher', 'admin']
    expires_at: str  # ISO format datetime
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionValidationResponse(BaseModel):
    """Lightweight validation response"""
    valid: bool
    user_id: Optional[str] = None