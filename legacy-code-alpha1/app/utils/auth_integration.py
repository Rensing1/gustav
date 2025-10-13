# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT
"""
Auth Integration Layer - Seamless transition between HttpOnly Cookies and Legacy Auth
This module provides a unified interface that automatically detects and uses
the appropriate authentication method.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
import streamlit as st
from datetime import datetime

# Import both auth systems
from utils.auth_session import AuthSession
from auth import sign_in as legacy_sign_in, sign_out as legacy_sign_out, get_user_role
from utils.secure_user import SecureUserDict

logger = logging.getLogger(__name__)


class AuthIntegration:
    """Unified authentication interface with automatic mode detection."""
    
    @staticmethod
    def detect_auth_mode() -> str:
        """Detect which authentication mode to use.
        
        Returns:
            'httponly' if Cookie Auth is available, 'legacy' otherwise
        """
        # Check environment variable override first
        auth_mode = os.getenv("AUTH_MODE", "").lower()
        if auth_mode in ["httponly", "legacy"]:
            logger.info(f"Auth mode set by environment: {auth_mode}")
            return auth_mode
        
        # Check if HttpOnly Cookie auth is available
        if AuthSession.get_current_user() is not None:
            logger.info("HttpOnly Cookie authentication detected")
            return "httponly"
        
        # Check if auth service is configured and reachable
        auth_service_url = AuthSession.get_auth_service_url()
        if auth_service_url and not auth_service_url.startswith("http://localhost"):
            # Production environment with auth service
            logger.info("Production environment - using HttpOnly Cookie auth")
            return "httponly"
        
        # Default to legacy in development or when auth service not configured
        logger.info("Using legacy authentication")
        return "legacy"
    
    @staticmethod
    def initialize_session() -> None:
        """Initialize session state with appropriate auth method."""
        # Ensure session state defaults
        if 'auth_mode' not in st.session_state:
            st.session_state.auth_mode = AuthIntegration.detect_auth_mode()
        
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'session' not in st.session_state:
            st.session_state.session = None
        if 'role' not in st.session_state:
            st.session_state.role = None
        
        # Try to sync with HttpOnly Cookie auth if available
        if st.session_state.auth_mode == "httponly":
            try:
                # Always sync in httponly mode to detect logouts
                AuthSession.sync_session_state()
                
                # Wrap user in SecureUserDict if exists
                if st.session_state.user and isinstance(st.session_state.user, dict):
                    try:
                        st.session_state.user = SecureUserDict(st.session_state.user)
                    except (TypeError, ValueError) as e:
                        logger.error(f"Could not wrap user in SecureUserDict: {e}")
                
                logger.info("Session synchronized with HttpOnly Cookies")
            except Exception as e:
                logger.warning(f"Could not sync HttpOnly session, falling back: {e}")
                st.session_state.auth_mode = "legacy"
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated with either method."""
        # Check HttpOnly Cookie auth first (if available)
        if st.session_state.get('auth_mode') == "httponly":
            return AuthSession.is_authenticated()
        
        # Fall back to legacy session state check
        return st.session_state.get('user') is not None
    
    @staticmethod
    def get_current_user() -> Optional[Any]:
        """Get current user info from appropriate auth method.
        
        Returns SecureUserDict for HttpOnly mode, original object/dict for legacy.
        """
        if st.session_state.get('auth_mode') == "httponly":
            user_dict = AuthSession.get_current_user()
            if user_dict:
                try:
                    # Wrap in SecureUserDict für Attribut-Zugriff
                    return SecureUserDict(user_dict)
                except (TypeError, ValueError) as e:
                    logger.error(f"Invalid user data: {e}")
                    return None
            return None
        
        # Legacy: return original user object (not wrapped)
        return st.session_state.get('user')
    
    @staticmethod
    def login(email: str, password: str) -> Tuple[bool, Optional[str]]:
        """Unified login method that tries appropriate auth system.
        
        Returns:
            (success, error_message)
        """
        # Determine auth mode
        auth_mode = st.session_state.get('auth_mode', AuthIntegration.detect_auth_mode())
        
        # Try HttpOnly Cookie auth first if available
        if auth_mode == "httponly":
            try:
                result = AuthSession.login(email, password)
                
                # Create user dict for SecureUserDict
                user_data = {
                    'id': result.get('user_id'),
                    'email': result.get('email'), 
                    'role': result.get('role')
                }
                
                # Update session state with SecureUserDict
                st.session_state.user = SecureUserDict(user_data)
                st.session_state.role = result.get('role')
                st.session_state.session = {'access_token': 'managed-by-cookies'}
                
                logger.info(f"Successful HttpOnly Cookie login for {email}")
                return (True, None)
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"HttpOnly Cookie login failed, trying legacy: {error_msg}")
                
                # If auth service is unavailable, fall back to legacy
                if "Verbindungsfehler" in error_msg or "Connection" in error_msg:
                    st.session_state.auth_mode = "legacy"
                else:
                    return (False, error_msg)
        
        # Use legacy authentication
        try:
            res = legacy_sign_in(email, password)
            
            if res.get("error"):
                return (False, res['error']['message'])
            elif res.get("user") and res.get("session"):
                # Check email confirmation
                if res["user"].email_confirmed_at is None:
                    return (False, "Bitte bestätigen Sie zuerst Ihre E-Mail-Adresse.")
                
                # Update session state
                st.session_state.session = res["session"]
                st.session_state.user = res["user"]
                st.session_state.role = get_user_role(res["user"].id)
                
                logger.info(f"Successful legacy login for {email}")
                return (True, None)
            else:
                return (False, "Anmeldung fehlgeschlagen")
                
        except Exception as e:
            logger.error(f"Legacy login error: {e}")
            return (False, f"Anmeldefehler: {str(e)}")
    
    @staticmethod
    def logout() -> Tuple[bool, Optional[str]]:
        """Unified logout method.
        
        Returns:
            (success, error_message)
        """
        logger.info("=== LOGOUT START ===")
        auth_mode = st.session_state.get('auth_mode', 'legacy')
        logger.info(f"Auth mode: {auth_mode}")
        
        # For HttpOnly Cookie mode, we need to redirect to the auth service logout page
        if auth_mode == "httponly":
            try:
                logger.info("Clearing local session state")
                # Clear local session state first
                st.session_state.user = None
                st.session_state.session = None
                st.session_state.role = None
                
                # Invalidate any cached clients
                logger.info("Invalidating user client")
                from utils.session_client import invalidate_user_client
                invalidate_user_client()
                
                # Clear auth session cache
                logger.info("Invalidating auth session cache")
                AuthSession.invalidate_cache()
                
                # Use Streamlit's navigation to redirect to logout page
                # This will trigger the auth service logout which clears the cookie
                # Use relative URL to work with nginx proxy
                logout_url = "/auth/logout"
                logger.info(f"Redirecting to {logout_url}")
                
                # Use st.switch_page or HTML redirect
                st.markdown(f'<meta http-equiv="refresh" content="0; url={logout_url}">', unsafe_allow_html=True)
                logger.info("=== LOGOUT END (REDIRECT) ===")
                st.stop()
                
            except Exception as e:
                logger.error(f"HttpOnly Cookie logout error: {e}", exc_info=True)
                logger.info("=== LOGOUT END (ERROR) ===")
                return (False, f"Logout-Fehler: {str(e)}")
        
        # Legacy logout for non-HttpOnly mode
        else:
            try:
                legacy_sign_out()
            except Exception as e:
                logger.warning(f"Legacy logout error: {e}")
            
            # Clear session state
            st.session_state.user = None
            st.session_state.session = None
            st.session_state.role = None
            
            # Invalidate any cached clients
            from utils.session_client import invalidate_user_client
            invalidate_user_client()
        
        return (True, None)
    
    @staticmethod
    def get_auth_status_message() -> str:
        """Get a user-friendly message about current auth status."""
        auth_mode = st.session_state.get('auth_mode', 'legacy')
        
        if auth_mode == "httponly":
            session_info = AuthSession.get_session_info()
            if session_info:
                expires_in = session_info.get('expires_in_seconds', 0)
                if expires_in > 0:
                    minutes = expires_in // 60
                    return f"🔒 Sichere Session (noch {minutes} Min. gültig)"
            return "🔒 Sichere Cookie-Authentifizierung aktiv"
        
        return "🔑 Standard-Authentifizierung"