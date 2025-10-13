"""
Forgot Password page for GUSTAV Auth Service
Handles password reset requests with HttpOnly cookie support
"""
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import structlog
import secrets
import time
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..config import settings
from ..services.supabase_client import supabase_service

logger = structlog.get_logger()

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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


def generate_csrf_token() -> str:
    """Generate a secure CSRF token"""
    return secrets.token_urlsafe(32)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    error: Optional[str] = None,
    success: Optional[str] = None,
    email: Optional[str] = None
):
    """Display forgot password form
    
    Args:
        request: FastAPI request
        error: Error message to display
        success: Success message to display
    """
    csrf_token = generate_csrf_token()
    
    error_messages = {
        "invalid_email": "Bitte geben Sie eine gültige E-Mail-Adresse ein.",
        "invalid_domain": "Nur E-Mail-Adressen mit @gymalf.de sind erlaubt.",
        "invalid_csrf": "Sicherheitsfehler. Bitte versuchen Sie es erneut.",
        "network_error": "Netzwerkfehler. Bitte versuchen Sie es später erneut.",
        "too_many_requests": "Zu viele Anfragen. Bitte warten Sie einige Minuten.",
    }
    
    success_messages = {
        "email_sent": "Ein 6-stelliger Code wurde an Ihre E-Mail-Adresse gesendet. Der Code ist 15 Minuten gültig.",
    }
    
    # Determine if running in secure context
    is_secure = request.url.scheme == "https" or settings.ENVIRONMENT != "production"
    
    logger.info("forgot_password_page_accessed",
                client_ip=request.client.host if request.client else "unknown",
                secure_context=is_secure)
    
    # Create response with template
    html_response = templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": error_messages.get(error, "") if error else None,
            "success": success_messages.get(success, "") if success else None,
            "email": email or "",
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


@router.post("/forgot-password")
async def process_forgot_password(
    request: Request,
    response: Response,
    email: str = Form(...),
    csrf_token: str = Form(...)
):
    """Process password reset request
    
    Args:
        request: FastAPI request
        response: FastAPI response
        email: Email address from form
        csrf_token: CSRF token from form
    """
    start_time = time.time()
    
    # CSRF validation
    csrf_cookie = request.cookies.get("csrf_token")
    if not csrf_cookie or csrf_cookie != csrf_token:
        logger.warning("forgot_password_csrf_validation_failed",
                      client_ip=request.client.host if request.client else "unknown")
        return RedirectResponse(url="/auth/forgot-password?error=invalid_csrf", status_code=303)
    
    # Email validation
    email = email.strip().lower()
    if not email:
        return RedirectResponse(url="/auth/forgot-password?error=invalid_email", status_code=303)
    
    # Domain validation
    if not validate_gymalf_email(email):
        logger.warning("forgot_password_invalid_domain_attempt",
                      email_domain=email.split('@')[-1] if '@' in email else "invalid")
        return RedirectResponse(url="/auth/forgot-password?error=invalid_domain", status_code=303)
    
    # Send OTP via Supabase
    try:
        # Send OTP for password reset
        result = await supabase_service.send_otp_for_password_reset(email)
        
        if not result.get("success"):
            logger.error("forgot_password_otp_send_failed",
                        error=result.get("error"),
                        email_hash=hash(email))
            # Check for rate limiting
            error_msg = result.get("error", {}).get("message", "")
            if "rate limit" in error_msg.lower() or "zu viele" in error_msg.lower():
                return RedirectResponse(url="/auth/forgot-password?error=too_many_requests", status_code=303)
            else:
                return RedirectResponse(url="/auth/forgot-password?error=network_error", status_code=303)
        
        logger.info("forgot_password_otp_sent",
                   email_hash=hash(email))
        
        # Timing attack protection - ensure constant response time
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await time.sleep(0.5 - elapsed)
            
        # Redirect with success and email parameter for pre-filling
        from urllib.parse import quote
        return RedirectResponse(url=f"/auth/forgot-password?success=email_sent&email={quote(email)}", status_code=303)
        
    except Exception as e:
        logger.error("forgot_password_unexpected_error",
                    error=str(e),
                    error_type=type(e).__name__)
        
        # Timing attack protection
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await time.sleep(0.5 - elapsed)
            
        return RedirectResponse(url="/auth/forgot-password?error=network_error", status_code=303)