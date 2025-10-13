"""
Authentication endpoints for GUSTAV
"""
from fastapi import APIRouter, Response, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import structlog
from typing import Optional

from app.models.auth import (
    LoginRequest, LoginResponse, LogoutResponse,
    SessionInfo, RefreshRequest, RefreshResponse,
    ErrorResponse
)
from app.models.session import Session
from app.services.secure_session_store import SecureSessionStore

# Initialize session store
session_store = SecureSessionStore()
from app.services.supabase_client import supabase_service
from app.config import settings
from app.dependencies import get_current_session_id

router = APIRouter(tags=["authentication"])
logger = structlog.get_logger()


@router.post("/api/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    response: Response
):
    """
    Login endpoint - validates credentials and sets HttpOnly cookie
    """
    try:
        # Log attempt
        logger.info("login_attempt", 
                   email=login_data.email,
                   ip=request.client.host if request.client else "unknown")
        
        # Authenticate with Supabase
        auth_result = await supabase_service.sign_in(
            email=login_data.email,
            password=login_data.password
        )
        
        if auth_result["error"]:
            logger.warning("login_failed", 
                          email=login_data.email,
                          error=auth_result["error"]["message"])
            raise HTTPException(
                status_code=401,
                detail=auth_result["error"]["message"]
            )
        
        user = auth_result["user"]
        supabase_session = auth_result["session"]
        
        # Debug: Log what we got from Supabase
        logger.info("supabase_auth_result",
                   has_user=user is not None,
                   has_session=supabase_session is not None,
                   session_type=type(supabase_session).__name__ if supabase_session else None,
                   session_attrs_sample=[attr for attr in dir(supabase_session) if not attr.startswith('_')][:10] if supabase_session else [])
        
        # Debug: Log session structure
        logger.debug("supabase_session_debug",
                    session_type=type(supabase_session).__name__,
                    session_dict=vars(supabase_session) if supabase_session else None,
                    has_access_token=hasattr(supabase_session, 'access_token') if supabase_session else False,
                    has_refresh_token=hasattr(supabase_session, 'refresh_token') if supabase_session else False,
                    has_expires_at=hasattr(supabase_session, 'expires_at') if supabase_session else False)
        
        # Get user profile with role
        profile = await supabase_service.get_user_profile(user.id)
        if not profile:
            logger.error("profile_not_found", user_id=user.id)
            raise HTTPException(
                status_code=500,
                detail="User profile not found"
            )
        
        # Debug: Check session attributes before storing
        session_data = None
        if supabase_session:
            try:
                session_data = {
                    "access_token": supabase_session.access_token,
                    "refresh_token": supabase_session.refresh_token,
                    "expires_at": supabase_session.expires_at
                }
                logger.info("session_data_prepared",
                           has_access_token=bool(session_data.get("access_token")),
                           has_refresh_token=bool(session_data.get("refresh_token")),
                           expires_at=session_data.get("expires_at"))
            except AttributeError as e:
                logger.error("session_attribute_error",
                            error=str(e),
                            session_type=type(supabase_session).__name__,
                            available_attrs=[attr for attr in dir(supabase_session) if not attr.startswith('_')])
                # Try to extract tokens differently
                if hasattr(supabase_session, '__dict__'):
                    logger.info("session_dict", data=supabase_session.__dict__)
        
        # Store in Supabase and get session_id
        session_id = await session_store.create_session(
            user_id=user.id,
            user_email=user.email,
            user_role=profile.get("role", "student"),
            data=session_data,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        # Create session object for response
        session = Session(
            user_id=user.id,
            email=user.email,
            role=profile.get("role", "student"),
            access_token=supabase_session.access_token,
            refresh_token=supabase_session.refresh_token,
            expires_at=supabase_session.expires_at,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            session_id=session_id
        )
        
        # Set HttpOnly cookie
        cookie_settings = settings.get_cookie_settings()
        response.set_cookie(**{
            **cookie_settings,
            "value": session.session_id
        })
        
        logger.info("login_successful",
                   user_id=user.id,
                   email=user.email,
                   role=session.role,
                   session_id=session.session_id)
        
        return LoginResponse(
            user_id=session.user_id,
            email=session.email,
            role=session.role,
            session_id=session.session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/api/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    session_id: Optional[str] = Depends(get_current_session_id)
):
    """
    Logout endpoint - clears session and cookie
    """
    if not session_id:
        # Already logged out
        return LogoutResponse()
    
    try:
        # Get session for logging
        session_data = await session_store.get_session(session_id)
        
        # Delete from Supabase
        await session_store.delete_session(session_id)
        
        # Clear cookie
        cookie_settings = settings.get_cookie_settings()
        response.delete_cookie(
            key=cookie_settings["key"],
            domain=cookie_settings["domain"],
            secure=cookie_settings["secure"],
            httponly=cookie_settings["httponly"],
            samesite=cookie_settings["samesite"]
        )
        
        if session_data:
            logger.info("logout_successful",
                       user_id=session_data.get("user_id"),
                       email=session_data.get("email"),
                       session_id=session_id)
        
        return LogoutResponse()
        
    except Exception as e:
        logger.error("logout_error", 
                    session_id=session_id,
                    error=str(e))
        # Still clear the cookie even if Redis fails
        cookie_settings = settings.get_cookie_settings()
        response.delete_cookie(key=cookie_settings["key"])
        return LogoutResponse()


@router.get("/verify")
async def verify_session(
    request: Request,
    session_id: Optional[str] = Depends(get_current_session_id)
):
    """
    Verify endpoint for nginx auth_request
    Returns 200 with headers if valid, 401 if not
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session")
    
    try:
        # Use the simplified session validation from secure session store
        validation_result = await session_store.validate_session(session_id)
        
        if not validation_result["is_valid"]:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        
        # Activity is automatically updated by validate_session
        
        # Return with auth headers for nginx
        headers = {
            "X-User-Id": validation_result["user_id"],
            "X-User-Email": validation_result["user_email"],
            "X-User-Role": validation_result["user_role"],
            "X-Session-Id": session_id,
            "X-Session-Expires": str(validation_result["expires_in_seconds"])
        }
        
        return Response(status_code=200, headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("session_verification_error",
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_data: Optional[RefreshRequest] = None,
    session_id: Optional[str] = Depends(get_current_session_id)
):
    """
    Refresh access token using refresh token
    Can use token from request body or current session
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session")
    
    try:
        # Get current session
        session_data = await session_store.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Parse session from Supabase format
        session = Session(
            user_id=session_data["user_id"],
            email=session_data["user_email"],
            role=session_data["user_role"],
            access_token=session_data["data"].get("access_token"),
            refresh_token=session_data["data"].get("refresh_token"),
            expires_at=session_data["data"].get("expires_at"),
            session_id=session_data["session_id"],
            ip_address=session_data.get("ip_address"),
            user_agent=session_data.get("user_agent")
        )
        
        # Use provided refresh token or session's token
        refresh_token = (
            refresh_data.refresh_token if refresh_data and refresh_data.refresh_token
            else session.refresh_token
        )
        
        # Refresh with Supabase
        refresh_result = await supabase_service.refresh_token(refresh_token)
        
        if refresh_result["error"]:
            logger.warning("manual_refresh_failed",
                          session_id=session_id,
                          error=refresh_result["error"]["message"])
            raise HTTPException(
                status_code=401,
                detail=refresh_result["error"]["message"]
            )
        
        # Update session
        new_supabase_session = refresh_result["session"]
        session.access_token = new_supabase_session.access_token
        session.refresh_token = new_supabase_session.refresh_token
        session.expires_at = new_supabase_session.expires_at
        session.update_activity()
        
        # Save updated session
        await session_store.update_session(
            session.session_id,
            {
                "access_token": new_supabase_session.access_token,
                "refresh_token": new_supabase_session.refresh_token,
                "expires_at": new_supabase_session.expires_at
            }
        )
        
        # Calculate expiration
        expires_in = session.expires_at - int(datetime.now(timezone.utc).timestamp())
        
        logger.info("manual_refresh_successful",
                   session_id=session_id,
                   expires_in=expires_in)
        
        return RefreshResponse(
            expires_in_seconds=max(0, expires_in)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("refresh_error",
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/session/info", response_model=SessionInfo)
async def get_session_info(
    session_id: str = Depends(get_current_session_id)
):
    """
    Get current session information
    Useful for debugging and user info display
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session")
    
    try:
        session_data = await session_store.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Parse session from Supabase format
        session = Session(
            user_id=session_data["user_id"],
            email=session_data["user_email"],
            role=session_data["user_role"],
            access_token=session_data["data"].get("access_token"),
            refresh_token=session_data["data"].get("refresh_token"),
            expires_at=session_data["data"].get("expires_at"),
            session_id=session_data["session_id"],
            ip_address=session_data.get("ip_address"),
            user_agent=session_data.get("user_agent")
        )
        
        # Calculate expiration
        expires_in = session.expires_at - int(datetime.now(timezone.utc).timestamp())
        
        return SessionInfo(
            user_id=session.user_id,
            email=session.email,
            role=session.role,
            session_id=session.session_id,
            expires_in_seconds=max(0, expires_in),
            last_activity=session.last_activity
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_session_info_error",
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")