"""
Authentication request/response models
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional


class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str = Field(..., min_length=6)
    
    @validator('email')
    def email_lowercase(cls, v):
        return v.lower()
    
    def __str__(self):
        """Never expose password in string representation"""
        return f"LoginRequest(email={self.email}, password=***)"
    
    def __repr__(self):
        """Never expose password in repr"""
        return f"LoginRequest(email={self.email}, password=***)"
    
    class Config:
        """Pydantic config to prevent password logging"""
        def schema_extra(schema, model_type):
            # Remove password from schema examples
            if 'password' in schema.get('properties', {}):
                schema['properties']['password']['example'] = "***"


class LoginResponse(BaseModel):
    """Login response model"""
    message: str = "Login successful"
    user_id: str
    email: str
    role: str
    session_id: str


class LogoutResponse(BaseModel):
    """Logout response model"""
    message: str = "Logged out successfully"


class SessionInfo(BaseModel):
    """Session information for verify endpoint"""
    user_id: str
    email: str
    role: str
    session_id: str
    expires_in_seconds: int
    last_activity: str


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: Optional[str] = None  # Can come from cookie


class RefreshResponse(BaseModel):
    """Token refresh response"""
    message: str = "Token refreshed successfully"
    expires_in_seconds: int


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    code: Optional[str] = None
    
    
class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str = "1.0.0"
    services: dict