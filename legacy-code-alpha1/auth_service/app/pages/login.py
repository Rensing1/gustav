# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Login Page Routes for GUSTAV Auth Service
Implements dedicated login page with secure CSRF protection
"""
from fastapi import APIRouter, Request, Form, Response, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import secrets
import logging
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse
import time
import asyncio

from ..services.supabase_session_store_secure import SecureSupabaseSessionStore
from ..config import settings
from ..dependencies import get_session_store
from ..models.auth import LoginRequest

logger = logging.getLogger(__name__)

# Setup templates directory
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()

def validate_redirect_url(next_url: str) -> str:
    """Validate redirect URL to prevent open redirect attacks.
    
    Args:
        next_url: The URL to validate
        
    Returns:
        Safe redirect URL (always internal)
    """
    if not next_url:
        return "/"
    
    parsed = urlparse(next_url)
    
    # No external redirects allowed
    if parsed.scheme or parsed.netloc:
        logger.warning(f"Blocked external redirect attempt: {next_url}")
        return "/"
    
    # Path must start with /
    if not parsed.path.startswith("/"):
        return "/"
    
    # Sanitize path to prevent traversal
    safe_path = parsed.path.replace("..", "")
    
    return safe_path


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    error: Optional[str] = None,
    next: Optional[str] = None,
    logout: Optional[str] = None,
    registered: Optional[bool] = None,
    csrf_cookie: Optional[str] = Cookie(None, alias="csrf_token")
):
    """Render the login page with secure CSRF protection using Double Submit Cookie pattern"""
    # Reuse existing CSRF token if present, otherwise generate new one
    # This prevents token mismatch when Streamlit health checks create multiple requests
    csrf_token = csrf_cookie if csrf_cookie else secrets.token_urlsafe(32)
    
    # Validate and sanitize redirect URL
    safe_next = validate_redirect_url(next)
    
    # Define error messages
    error_messages = {
        "invalid_credentials": "E-Mail oder Passwort falsch.",
        "invalid_csrf": "Sicherheitsfehler. Bitte erneut versuchen.",
        "rate_limit": "Zu viele Anmeldeversuche. Bitte später erneut versuchen.",
        "email_not_confirmed": "E-Mail-Adresse noch nicht bestätigt.",
        "account_locked": "Account gesperrt. Bitte kontaktieren Sie den Support."
    }
    
    # Create the template response
    html_response = templates.TemplateResponse("login.html", {
        "request": request,
        "csrf_token": csrf_token,
        "error": error,
        "error_messages": error_messages,
        "next": safe_next,
        "title": "GUSTAV Login",
        "logout_success": logout == "success",
        "registered": registered
    })
    
    # Only set CSRF cookie if it's a new token (not reused from existing cookie)
    if not csrf_cookie or csrf_cookie != csrf_token:
        # Set CSRF cookie on the actual response object
        # CSRF cookies don't need to be secure as they're single-use and don't contain sensitive data
        # This fixes the issue where HTTPS->nginx->HTTP prevents cookie reading
        logger.warning(f"Setting NEW CSRF cookie: token={csrf_token[:8]}..., secure=False (CSRF-only), domain={settings.COOKIE_DOMAIN if settings.ENVIRONMENT == 'production' else 'None'}")
        logger.warning(f"Request scheme: {request.url.scheme}, Environment: {settings.ENVIRONMENT}")
        
        html_response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=True,
            secure=False,  # CSRF tokens don't need secure flag - fixes nginx proxy issues
            samesite="lax",  # Changed from strict to lax for better compatibility
            max_age=3600,  # 1 hour
            path="/auth",  # No trailing slash - includes /auth/login
            domain=settings.COOKIE_DOMAIN if settings.ENVIRONMENT == "production" else None
        )
    else:
        logger.info(f"Reusing existing CSRF token: {csrf_token[:8]}...")
    
    return html_response


@router.post("/login")
async def process_login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    csrf_form: str = Form(..., alias="csrf_token"),
    next: str = Form("/"),
    csrf_cookie: Optional[str] = Cookie(None, alias="csrf_token"),
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
):
    """Process login with secure CSRF validation and session regeneration"""
    # Import here to avoid circular dependency
    from ..routes.login import authenticate_user
    
    # Timing attack prevention - start timer
    start_time = time.time()
    
    # Validate CSRF (Double Submit Cookie)
    logger.warning(f"CSRF Debug: cookie={csrf_cookie[:8] if csrf_cookie else 'None'}..., form={csrf_form[:8] if csrf_form else 'None'}...")
    logger.warning(f"CSRF Full comparison: cookie_len={len(csrf_cookie) if csrf_cookie else 0}, form_len={len(csrf_form) if csrf_form else 0}")
    logger.warning(f"Request headers: {dict(request.headers)}")
    logger.warning(f"All cookies: {list(request.cookies.keys())}")
    
    if not csrf_cookie or csrf_cookie != csrf_form:
        logger.warning(f"CSRF validation failed from {request.client.host if request.client else 'unknown'}: cookie={'present' if csrf_cookie else 'missing'}, form={'present' if csrf_form else 'missing'}")
        if csrf_cookie and csrf_form:
            logger.warning(f"CSRF mismatch details: cookie != form, but both present")
            logger.warning(f"Cookie value: {csrf_cookie}")
            logger.warning(f"Form value: {csrf_form}")
        return RedirectResponse(
            url="/auth/login?error=invalid_csrf",
            status_code=303
        )
    
    # Validate and sanitize redirect URL
    safe_next = validate_redirect_url(next)
    
    # Session fixation prevention - get old session ID
    old_session_id = request.cookies.get(settings.COOKIE_NAME)
    
    try:
        # Use existing authentication logic
        login_data = LoginRequest(email=email, password=password)
        user_data = await authenticate_user(login_data, session_store)
        
        if not user_data:
            # Timing attack prevention - ensure constant response time
            elapsed = time.time() - start_time
            if elapsed < 0.5:  # Minimum 500ms response time
                await asyncio.sleep(0.5 - elapsed)
            
            return RedirectResponse(
                url="/auth/login?error=invalid_credentials",
                status_code=303
            )
        
        # Session fixation prevention - invalidate old session
        if old_session_id:
            try:
                await session_store.delete_session(old_session_id)
                logger.info(f"Invalidated old session {old_session_id[:8]}... for user {user_data['id']}")
            except Exception as e:
                logger.error(f"Failed to invalidate old session: {e}")
        
        # Create NEW session with NEW ID (session regeneration)
        # Extract tokens safely with defensive programming
        session_data = None
        if user_data.get("access_token") and user_data.get("refresh_token"):
            session_data = {
                "access_token": user_data["access_token"],
                "refresh_token": user_data["refresh_token"],
                "expires_at": user_data.get("expires_at")
            }
            logger.info(f"Session tokens prepared for storage",
                       user_id=user_data["id"],
                       has_tokens=True)
        else:
            logger.warning(f"No session tokens available for user {user_data['id']}",
                          has_access_token=bool(user_data.get("access_token")),
                          has_refresh_token=bool(user_data.get("refresh_token")))
        
        session_id = await session_store.create_session(
            user_id=user_data["id"],
            user_email=user_data["email"],
            user_role=user_data.get("role", "user"),
            data=session_data,  # Include token data for navigation proxy
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info(f"Created new session {session_id[:8]}... for user {user_data['id']}",
                   with_tokens=bool(session_data))
        
        # Set session cookie
        cookie_settings = settings.get_cookie_settings()
        response = RedirectResponse(url=safe_next, status_code=303)
        response.set_cookie(
            key=cookie_settings["key"],
            value=session_id,
            max_age=cookie_settings["max_age"],
            httponly=cookie_settings["httponly"],
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            domain=cookie_settings["domain"]
        )
        
        # Clear CSRF cookie after successful login
        response.delete_cookie(key="csrf_token", path="/auth")
        
        logger.info(f"Successful login for {email} via login page with session regeneration")
        return response
        
    except HTTPException as e:
        # Handle specific errors with timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
            
        error_code = "invalid_credentials"  # Default safe error
        
        if e.status_code == 429:
            error_code = "rate_limit"
        elif e.detail and "not confirmed" in e.detail.lower():
            error_code = "email_not_confirmed"
        elif e.detail and "locked" in e.detail.lower():
            error_code = "account_locked"
            
        return RedirectResponse(
            url=f"/auth/login?error={error_code}",
            status_code=303
        )
    except Exception as e:
        # Timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
            
        logger.error(f"Login error: {e}")
        return RedirectResponse(
            url="/auth/login?error=invalid_credentials",
            status_code=303
        )


@router.get("/logout")
async def direct_logout(
    request: Request,
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
):
    """Direct logout without confirmation page"""
    logger.info(f"=== DIRECT LOGOUT REQUEST ===")
    
    # Get session from cookie
    session_id = request.cookies.get(settings.COOKIE_NAME)
    logger.info(f"Session to delete: {session_id[:16] if session_id else 'None'}...")
    
    if session_id:
        try:
            # Delete session from store
            await session_store.delete_session(session_id)
            logger.info(f"Session {session_id[:8]}... deleted from store")
        except Exception as e:
            logger.error(f"Error deleting session: {e}", exc_info=True)
    
    # Create response and clear cookies
    response = RedirectResponse(url="/auth/login?logout=success", status_code=303)
    
    # Delete session cookie with all possible variations
    cookie_domain = settings.COOKIE_DOMAIN if settings.ENVIRONMENT == "production" else None
    logger.info(f"Deleting cookie: key={settings.COOKIE_NAME}, domain={cookie_domain}, path=/")
    
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=cookie_domain,
        path="/"
    )
    
    # Also delete any CSRF cookies
    response.delete_cookie(key="csrf_token", path="/auth")
    
    logger.info(f"=== DIRECT LOGOUT COMPLETE ===")
    
    return response


# POST logout route removed - using direct GET logout instead