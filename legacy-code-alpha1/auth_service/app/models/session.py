"""
Session models for Auth Service
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import secrets
import string


def generate_session_id() -> str:
    """Generate a secure random session ID"""
    # Use URL-safe characters for compatibility
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(32))


class Session(BaseModel):
    """Session data model stored in Redis"""
    
    session_id: str = Field(default_factory=generate_session_id)
    user_id: str
    email: str
    role: str = "student"
    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Optional metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now(timezone.utc).timestamp() > self.expires_at
    
    def needs_refresh(self, buffer_seconds: int = 300) -> bool:
        """Check if token needs refresh (with 5-minute buffer by default)"""
        return datetime.now(timezone.utc).timestamp() > (self.expires_at - buffer_seconds)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now(timezone.utc).isoformat()
    
    def to_headers(self) -> dict:
        """Convert session to nginx headers"""
        return {
            "X-User-Id": self.user_id,
            "X-User-Email": self.email,
            "X-User-Role": self.role,
            "X-Access-Token": self.access_token,
            "X-Session-Id": self.session_id
        }
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }