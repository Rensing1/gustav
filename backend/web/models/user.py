"""
User Model for GUSTAV

This file defines the User model that will be used throughout the application.
It integrates with Supabase Auth and provides type safety for all components.

TODO: Implement after UI is complete
- Integrate with Supabase Auth
- Add session management with Redis
- Implement get_current_user dependency
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from uuid import UUID
from datetime import datetime


class UserRole(str, Enum):
    """User roles in GUSTAV"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(BaseModel):
    """User model with full type safety

    This model will be used:
    - In FastAPI dependencies
    - For session storage (Redis)
    - In UI components
    - For Supabase integration
    """
    id: UUID
    email: str
    name: str
    role: UserRole
    created_at: Optional[datetime] = None

    # Additional fields for GUSTAV
    school_id: Optional[UUID] = None
    avatar_url: Optional[str] = None

    class Config:
        # Allow ORM mode for Supabase responses
        orm_mode = True
        # Use enum values in JSON
        use_enum_values = True

        # Example for documentation
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "max.mustermann@schule.de",
                "name": "Max Mustermann",
                "role": "student",
                "school_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


# Temporary mock for UI development
def get_mock_user(role: str = "student") -> dict:
    """Get a mock user dict for UI development

    This will be replaced with real Supabase auth later.
    Returns a dict for now to match current component expectations.
    """
    users = {
        "student": {
            "id": "mock-student-id",
            "email": "schueler@gustav.de",
            "name": "Max Musterschüler",
            "role": "student"
        },
        "teacher": {
            "id": "mock-teacher-id",
            "email": "lehrer@gustav.de",
            "name": "Dr. Lisa Lehrerin",
            "role": "teacher"
        },
        "admin": {
            "id": "mock-admin-id",
            "email": "admin@gustav.de",
            "name": "Admin Administrator",
            "role": "admin"
        }
    }
    return users.get(role, users["student"])


# TODO: Implement after UI
"""
Future implementation:

from fastapi import Depends, Request, HTTPException
from app.auth import get_session

async def get_current_user(request: Request) -> User:
    # Get session from httpOnly cookie
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(401, "Not authenticated")

    # Get user data from session store
    user_data = await get_session(session_id)
    if not user_data:
        raise HTTPException(401, "Session expired")

    # Return validated User model
    return User(**user_data)
"""