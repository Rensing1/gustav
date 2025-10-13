# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Authentication helper for login page routes
Contains the authenticate_user function used by the login page
"""
from typing import Optional, Dict, Any
import logging

from ..services.supabase_session_store_secure import SecureSupabaseSessionStore
from ..services.supabase_client import supabase_service
from ..models.auth import LoginRequest

logger = logging.getLogger(__name__)


async def authenticate_user(
    login_data: LoginRequest,
    session_store: SecureSupabaseSessionStore
) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with Supabase and return user data if successful
    
    Args:
        login_data: Login credentials
        session_store: Session store instance
        
    Returns:
        User data dict with id, email, role, and session tokens if successful, None otherwise
    """
    try:
        # Authenticate with Supabase
        auth_result = await supabase_service.sign_in(
            email=login_data.email,
            password=login_data.password
        )
        
        if auth_result["error"]:
            logger.warning(f"Login failed for {login_data.email}: {auth_result['error']['message']}")
            return None
        
        user = auth_result["user"]
        session = auth_result["session"]
        
        # Verify we have a valid session with tokens
        if not session:
            logger.error(f"No session returned for user {user.id}")
            return None
            
        # Get user profile with role
        profile = await supabase_service.get_user_profile(user.id)
        if not profile:
            logger.error(f"Profile not found for user {user.id}")
            return None
        
        # Log successful auth without exposing tokens
        logger.info(f"User authenticated successfully", 
                   user_id=user.id,
                   has_access_token=bool(session.access_token),
                   has_refresh_token=bool(session.refresh_token))
        
        # Return user data WITH session tokens for session storage
        # IMPORTANT: These tokens will be stored securely in the session DB
        # and are needed for the navigation proxy to work
        return {
            "id": user.id,
            "email": user.email,
            "role": profile.get("role", "student"),
            # Add session tokens for proxy functionality
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at
        }
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None