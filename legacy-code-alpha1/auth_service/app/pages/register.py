# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Register Page Routes for GUSTAV Auth Service
Implements user registration with @gymalf.de domain restriction
"""
from fastapi import APIRouter, Request, Form, Response, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import secrets
import logging
from pathlib import Path
import time
import asyncio
import re

from ..services.supabase_client import supabase_service
from ..config import settings

logger = logging.getLogger(__name__)

# Setup templates directory
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()


def validate_gymalf_email(email: str) -> bool:
    """
    Validates that email belongs to @gymalf.de domain
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if email is valid @gymalf.de address
    """
    if not email:
        return False
    
    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    
    # Domain validation
    return email.lower().endswith("@gymalf.de")


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password meets minimum requirements
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Passwort muss mindestens 8 Zeichen lang sein."
    
    # Additional checks can be added here
    # For now, just length requirement
    
    return True, ""


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    error: Optional[str] = None
):
    """Render the registration page with CSRF protection"""
    # Generate CSRF token
    csrf_token = secrets.token_urlsafe(32)
    
    # Define error messages
    error_messages = {
        "invalid_domain": "Nur E-Mail-Adressen mit @gymalf.de sind erlaubt.",
        "email_exists": "Diese E-Mail-Adresse ist bereits registriert.",
        "password_mismatch": "Die Passwörter stimmen nicht überein.",
        "password_weak": "Passwort muss mindestens 8 Zeichen lang sein.",
        "invalid_csrf": "Sicherheitsfehler. Bitte erneut versuchen.",
        "registration_failed": "Registrierung fehlgeschlagen. Bitte erneut versuchen.",
        "rate_limit": "Zu viele Registrierungsversuche. Bitte später erneut versuchen."
    }
    
    # Create the template response
    html_response = templates.TemplateResponse("register.html", {
        "request": request,
        "csrf_token": csrf_token,
        "error": error,
        "error_messages": error_messages,
        "title": "GUSTAV Registrierung"
    })
    
    # Set CSRF cookie
    html_response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=False,  # CSRF tokens don't need secure flag
        samesite="lax",
        max_age=3600,  # 1 hour
        path="/auth",
        domain=settings.COOKIE_DOMAIN if settings.ENVIRONMENT == "production" else None
    )
    
    return html_response


@router.post("/register")
async def process_register(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_form: str = Form(..., alias="csrf_token"),
    csrf_cookie: Optional[str] = Cookie(None, alias="csrf_token")
):
    """Process registration with domain validation and CSRF protection"""
    # Timing attack prevention - start timer
    start_time = time.time()
    
    # Validate CSRF (Double Submit Cookie)
    if not csrf_cookie or csrf_cookie != csrf_form:
        logger.warning(f"CSRF validation failed during registration from {request.client.host if request.client else 'unknown'}")
        return RedirectResponse(
            url="/auth/register?error=invalid_csrf",
            status_code=303
        )
    
    # Validate domain restriction
    if not validate_gymalf_email(email):
        logger.warning(f"Registration attempt with invalid domain: {email}")
        # Timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
        return RedirectResponse(
            url="/auth/register?error=invalid_domain",
            status_code=303
        )
    
    # Validate passwords match
    if password != password_confirm:
        # Timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
        return RedirectResponse(
            url="/auth/register?error=password_mismatch",
            status_code=303
        )
    
    # Validate password strength
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        # Timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
        return RedirectResponse(
            url="/auth/register?error=password_weak",
            status_code=303
        )
    
    try:
        # Attempt registration with Supabase
        result = await supabase_service.sign_up(email, password)
        
        if result.get("error"):
            error_msg = result["error"].get("message", "")
            error_code = "registration_failed"
            
            # Map specific errors
            if "already registered" in error_msg.lower() or "user already registered" in error_msg.lower():
                error_code = "email_exists"
            elif "rate limit" in error_msg.lower():
                error_code = "rate_limit"
            
            logger.warning(f"Registration failed for {email}: {error_msg}")
            
            # Timing attack prevention
            elapsed = time.time() - start_time
            if elapsed < 0.5:
                await asyncio.sleep(0.5 - elapsed)
                
            return RedirectResponse(
                url=f"/auth/register?error={error_code}",
                status_code=303
            )
        
        # Registration successful
        logger.info(f"Successful registration for {email}")
        
        # Clear CSRF cookie
        response = RedirectResponse(
            url="/auth/login?registered=true",
            status_code=303
        )
        response.delete_cookie(key="csrf_token", path="/auth")
        
        return response
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        
        # Timing attack prevention
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            await asyncio.sleep(0.5 - elapsed)
            
        return RedirectResponse(
            url="/auth/register?error=registration_failed",
            status_code=303
        )