"""
FastAPI dependencies for Auth Service
"""
from fastapi import Request, HTTPException
from typing import Optional
import structlog

from app.config import settings
from app.services.secure_session_store import SecureSessionStore as SecureSupabaseSessionStore

logger = structlog.get_logger()

# Global session store instance
_session_store = None

def get_session_store() -> SecureSupabaseSessionStore:
    """
    Get the global session store instance
    
    Returns:
        SecureSupabaseSessionStore instance
    """
    global _session_store
    if _session_store is None:
        _session_store = SecureSupabaseSessionStore()
    return _session_store


async def get_current_session_id(request: Request) -> Optional[str]:
    """
    Extract session ID from cookie or Authorization header
    
    Args:
        request: FastAPI request object
    
    Returns:
        Session ID string or None if not found
    """
    # Try cookie first (primary method)
    session_id = request.cookies.get(settings.COOKIE_NAME)
    
    if session_id:
        logger.debug("session_id_from_cookie", session_id=session_id)
        return session_id
    
    # Try Authorization header as fallback (for API clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        session_id = auth_header[7:]  # Remove "Bearer " prefix
        logger.debug("session_id_from_header", session_id=session_id)
        return session_id
    
    return None


async def require_session(session_id: Optional[str] = None) -> str:
    """
    Require a valid session ID
    
    Args:
        session_id: Optional session ID from get_current_session_id
    
    Returns:
        Valid session ID
        
    Raises:
        HTTPException: 401 if no session
    """
    if not session_id:
        logger.warning("required_session_missing")
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    return session_id