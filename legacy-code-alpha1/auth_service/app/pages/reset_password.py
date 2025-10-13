"""
Reset Password page for GUSTAV Auth Service
Handles password reset with OTP verification
"""
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import structlog
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
import re

from ..config import settings
from ..services.supabase_client import supabase_service
from ..services.supabase_session_store_secure import SecureSupabaseSessionStore

logger = structlog.get_logger()

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
session_store = SecureSupabaseSessionStore()


def generate_csrf_token() -> str:
    """Generate a secure CSRF token"""
    return secrets.token_urlsafe(32)


def validate_password(password: str) -> tuple[bool, Optional[str]]:
    """Validate password requirements
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Passwort darf nicht leer sein."
    
    if len(password) < 8:
        return False, "Passwort muss mindestens 8 Zeichen lang sein."
    
    return True, None


def validate_gymalf_email(email: str) -> bool:
    """Validate email domain is @gymalf.de
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email ends with @gymalf.de, False otherwise
    """
    if not email:
        return False
    
    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    
    # Domain validation - must be exactly @gymalf.de
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@gymalf\.de$', email.lower().strip()))


def validate_otp(otp: str) -> bool:
    """Validate OTP format
    
    Args:
        otp: OTP code to validate
        
    Returns:
        True if OTP is valid format (6 digits), False otherwise
    """
    if not otp:
        return False
    
    # Remove any spaces or dashes
    otp = otp.replace(" ", "").replace("-", "")
    
    # Check if it's exactly 6 digits
    return bool(re.match(r'^\d{6}$', otp))


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    error: Optional[str] = None,
    email: Optional[str] = None
):
    """Display reset password form with OTP input
    
    Args:
        request: FastAPI request
        error: Error message to display
        email: Pre-filled email address (from forgot-password flow)
    """
    csrf_token = generate_csrf_token()
    
    error_messages = {
        "invalid_email": "Bitte geben Sie eine gültige E-Mail-Adresse ein.",
        "invalid_domain": "Nur E-Mail-Adressen mit @gymalf.de sind erlaubt.",
        "invalid_otp": "Der eingegebene Code ist ungültig. Bitte prüfen Sie Ihre Eingabe.",
        "expired_otp": "Der Code ist abgelaufen. Bitte fordern Sie einen neuen Code an.",
        "password_mismatch": "Die Passwörter stimmen nicht überein.",
        "password_too_short": "Passwort muss mindestens 8 Zeichen lang sein.",
        "invalid_csrf": "Sicherheitsfehler. Bitte versuchen Sie es erneut.",
        "update_failed": "Passwort konnte nicht aktualisiert werden. Bitte versuchen Sie es erneut.",
        "too_many_attempts": "Zu viele fehlgeschlagene Versuche. Bitte fordern Sie einen neuen Code an.",
    }
    
    # Determine if running in secure context
    is_secure = request.url.scheme == "https" or settings.ENVIRONMENT != "production"
    
    logger.info("reset_password_page_accessed",
                client_ip=request.client.host if request.client else "unknown",
                secure_context=is_secure,
                has_email=bool(email))
    
    # Create response with template
    html_response = templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": error_messages.get(error, "") if error else None,
            "email": email,
        }
    )
    
    # Set CSRF cookie
    html_response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=False,  # CSRF tokens don't need secure flag
        samesite="lax",
        max_age=3600,  # 1 hour
        path="/auth"
    )
    
    return html_response


@router.post("/reset-password")
async def process_reset_password(
    request: Request,
    response: Response,
    email: str = Form(...),
    otp: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...)
):
    """Process password reset with OTP verification
    
    Args:
        request: FastAPI request
        response: FastAPI response
        email: User email address
        otp: 6-digit OTP code
        password: New password
        confirm_password: Password confirmation
        csrf_token: CSRF token from form
    """
    start_time = time.time()
    
    # CSRF validation
    csrf_cookie = request.cookies.get("csrf_token")
    if not csrf_cookie or csrf_cookie != csrf_token:
        logger.warning("reset_password_csrf_validation_failed",
                      client_ip=request.client.host if request.client else "unknown")
        return RedirectResponse(url="/auth/reset-password?error=invalid_csrf", 
                              status_code=303)
    
    # Email validation
    email = email.strip().lower()
    if not email:
        return RedirectResponse(url="/auth/reset-password?error=invalid_email", 
                              status_code=303)
    
    # Domain validation
    if not validate_gymalf_email(email):
        logger.warning("reset_password_invalid_domain_attempt",
                      email_domain=email.split('@')[-1] if '@' in email else "invalid")
        return RedirectResponse(url="/auth/reset-password?error=invalid_domain", 
                              status_code=303)
    
    # OTP validation
    otp = otp.replace(" ", "").replace("-", "")  # Clean OTP input
    if not validate_otp(otp):
        logger.warning("reset_password_invalid_otp_format",
                      email_hash=hash(email))
        return RedirectResponse(url=f"/auth/reset-password?error=invalid_otp&email={email}", 
                              status_code=303)
    
    # Password validation
    if password != confirm_password:
        return RedirectResponse(url=f"/auth/reset-password?error=password_mismatch&email={email}", 
                              status_code=303)
    
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return RedirectResponse(url=f"/auth/reset-password?error=password_too_short&email={email}", 
                              status_code=303)
    
    try:
        # Verify OTP and update password
        result = await supabase_service.verify_otp_and_update_password(email, otp, password)
        
        if result.get("error"):
            logger.error("reset_password_otp_verification_failed",
                        error=result["error"],
                        email_hash=hash(email))
            
            error_msg = result["error"].get("message", "")
            if "ungültig" in error_msg.lower() or "abgelaufen" in error_msg.lower():
                return RedirectResponse(url=f"/auth/reset-password?error=expired_otp&email={email}", 
                                      status_code=303)
            elif "zu viele" in error_msg.lower():
                return RedirectResponse(url="/auth/reset-password?error=too_many_attempts", 
                                      status_code=303)
            else:
                return RedirectResponse(url=f"/auth/reset-password?error=update_failed&email={email}", 
                                      status_code=303)
        
        # Get user data and session from result
        user_data = result.get("user")
        session_data = result.get("session")
        
        if not user_data or not session_data:
            logger.error("reset_password_no_user_or_session")
            return RedirectResponse(url="/auth/login?error=session_error", status_code=303)
        
        # Get user profile for role
        profile = await supabase_service.get_user_profile(user_data.id)
        user_role = profile.get("role", "student") if profile else "student"
        
        # Create session in our session store
        session_id = await session_store.create_session(
            user_id=user_data.id,
            user_email=user_data.email,
            user_role=user_role
        )
        
        logger.info("reset_password_success",
                   user_id=user_data.id,
                   email_hash=hash(user_data.email))
        
        # Timing attack protection
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
        
        # Set session cookie and redirect to app
        response = RedirectResponse(url=settings.APP_URL, status_code=303)
        
        # Determine if running in secure context
        is_secure = request.url.scheme == "https" or settings.ENVIRONMENT != "production"
        
        cookie_settings = settings.get_cookie_settings()
        response.set_cookie(
            key=cookie_settings["key"],
            value=session_id,
            max_age=cookie_settings["max_age"],
            httponly=cookie_settings["httponly"],
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            domain=cookie_settings["domain"],
            path="/"
        )
        
        return response
        
    except Exception as e:
        logger.error("reset_password_unexpected_error",
                    error=str(e),
                    error_type=type(e).__name__)
        
        # Timing attack protection
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
            
        return RedirectResponse(url=f"/auth/reset-password?error=update_failed&email={email}", 
                              status_code=303)