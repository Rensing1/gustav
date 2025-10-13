"""
Session management endpoints for GUSTAV
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime, timezone, timedelta
import structlog
from typing import Optional

from app.models.session_response import SessionResponse, SessionValidationResponse
from app.dependencies import get_session_store
from app.services.secure_session_store import SecureSessionStore

router = APIRouter(prefix="/session", tags=["session"])
logger = structlog.get_logger()


@router.get("/me", response_model=SessionResponse)
async def get_current_session(
    request: Request,
    session_store: SecureSessionStore = Depends(get_session_store)
):
    """Get current user session data from cookie"""
    session_id = request.cookies.get("gustav_session")
    if not session_id:
        logger.warning("session_me_no_cookie", ip=request.client.host if request.client else "unknown")
        raise HTTPException(401, "No session cookie")
    
    try:
        # Validate session and get user data
        result = await session_store.validate_session(session_id)
        
        if not result["is_valid"]:
            logger.warning("session_me_invalid", 
                         session_id=session_id[:8] + "...",
                         ip=request.client.host if request.client else "unknown")
            raise HTTPException(401, "Invalid or expired session")
        
        # Get full session data for response
        session_data = await session_store.get_session(session_id)
        if not session_data:
            raise HTTPException(401, "Session not found")
        
        logger.info("session_me_success", 
                   user_id=result["user_id"],
                   ip=request.client.host if request.client else "unknown")
        
        # Calculate expires_at from expires_in_seconds
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.get("expires_in_seconds", 0))
        
        return SessionResponse(
            user_id=result["user_id"],
            email=result.get("user_email") or result.get("email"),  # Handle both formats
            role=result.get("user_role") or result.get("role"),     # Handle both formats
            expires_at=expires_at.isoformat(),
            metadata={
                "last_activity": session_data.get("last_activity"),
                "created_at": session_data.get("created_at"),
                "ip_address": session_data.get("ip_address"),
                "user_agent": session_data.get("user_agent")
            }
        )
    
    except Exception as e:
        logger.error("session_me_error", 
                    error=str(e),
                    ip=request.client.host if request.client else "unknown")
        raise HTTPException(500, "Internal server error")


@router.get("/validate", response_model=SessionValidationResponse)
async def validate_session_lightweight(
    request: Request,
    session_store: SecureSessionStore = Depends(get_session_store)
):
    """Lightweight validation endpoint"""
    session_id = request.cookies.get("gustav_session")
    if not session_id:
        return SessionValidationResponse(valid=False)
    
    try:
        result = await session_store.validate_session(session_id)
        return SessionValidationResponse(
            valid=result["is_valid"],
            user_id=result.get("user_id") if result["is_valid"] else None
        )
    except Exception as e:
        logger.error("session_validate_error", error=str(e))
        return SessionValidationResponse(valid=False)