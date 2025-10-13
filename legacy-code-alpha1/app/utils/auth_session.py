# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT
"""
HttpOnly Cookie Authentication Session Management für GUSTAV
Session-basierte Integration mit Auth Service
"""

import os
import asyncio
import time
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timedelta
import streamlit as st
import requests
from urllib.parse import urljoin, urlparse
import logging
import threading
from functools import lru_cache
import ipaddress

logger = logging.getLogger(__name__)


def create_test_session(email: str, role: str) -> Optional[Dict[str, Any]]:
    """
    Erstellt eine Test-Session für CLI-Tests.
    
    Args:
        email: E-Mail des Benutzers
        role: Rolle ('teacher' oder 'student')
    
    Returns:
        Session-Daten mit id und session_id
    """
    try:
        # Simuliere Session-Daten
        import uuid
        from utils.config import get_supabase_credentials
        
        # Hole Anon-Client für User-Lookup
        from utils.db.core.session import get_anon_client
        client = get_anon_client()
        
        # Suche User in profiles
        result = client.table('profiles').select('*').eq('email', email).single().execute()
        
        if hasattr(result, 'data') and result.data:
            user_data = result.data
            # Erstelle Mock-Session
            session_data = {
                'id': user_data['id'],
                'email': user_data['email'],
                'role': user_data['role'],
                'display_name': user_data.get('display_name'),
                'session_id': f"test_{uuid.uuid4().hex[:16]}",  # Mock session ID
                'is_test': True
            }
            
            # Setze in session_state für get_session_id()
            import streamlit as st
            if 'auth_session_id' not in st.session_state:
                st.session_state.auth_session_id = session_data['session_id']
            
            return session_data
        else:
            print(f"User {email} nicht gefunden")
            return None
            
    except Exception as e:
        print(f"Fehler beim Erstellen der Test-Session: {e}")
        return None


class AuthSession:
    """Handles authentication state via session-based Auth Service integration."""
    
    # Cache configuration
    CACHE_DURATION = timedelta(minutes=5)
    _fetch_lock = threading.Lock()
    _pending_fetch = None
    
    # Security: Whitelist for Auth Service URLs
    ALLOWED_AUTH_HOSTS = {
        'auth:8000',              # Docker internal
        'localhost:8000',         # Development  
        'auth-service:8000',      # K8s service
    }
    
    @staticmethod
    def validate_auth_url(url: str) -> bool:
        """Validate auth service URL against whitelist to prevent SSRF."""
        try:
            parsed = urlparse(url)
            
            # Check against whitelist
            if parsed.netloc in AuthSession.ALLOWED_AUTH_HOSTS:
                return True
            
            # Prevent IP-based attacks
            host = parsed.hostname
            if host:
                try:
                    # Block private IPs
                    ip = ipaddress.ip_address(host)
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        logger.warning(f"Blocked private IP access attempt: {host}")
                        return False
                except ValueError:
                    # Not an IP, check if it's in whitelist
                    pass
                    
            logger.warning(f"Auth URL not in whitelist: {url}")
            return False
        except Exception as e:
            logger.error(f"Error validating auth URL: {e}")
            return False
    
    @staticmethod
    def get_auth_service_url() -> str:
        """Get the auth service URL from config."""
        url = os.getenv("AUTH_SERVICE_URL", "http://auth:8000")
        
        # Validate URL for security
        if not AuthSession.validate_auth_url(url):
            # Fallback to safe default
            logger.error(f"Invalid AUTH_SERVICE_URL: {url}, using default")
            return "http://auth:8000"
        
        return url
    
    @staticmethod
    def _fetch_session_from_auth() -> Optional[Dict[str, Any]]:
        """Fetch session data from auth service synchronously."""
        logger.info("=== FETCH SESSION FROM AUTH START ===")
        cookie = None
        
        # Get session cookie
        if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
            all_cookies = dict(st.context.cookies)
            logger.info(f"Available cookies: {list(all_cookies.keys())}")
            cookie = st.context.cookies.get('gustav_session')
            if cookie:
                logger.info(f"Found gustav_session cookie: {cookie[:16]}...")
        else:
            logger.warning("st.context.cookies not available")
        
        if not cookie:
            logger.info("No session cookie found in request")
            logger.info("=== FETCH SESSION FROM AUTH END (NO COOKIE) ===")
            return None
        
        auth_service_url = AuthSession.get_auth_service_url()
        logger.info(f"Auth service URL: {auth_service_url}")
        
        try:
            logger.info(f"Requesting {auth_service_url}/auth/session/me with cookie: {cookie[:16]}...")
            response = requests.get(
                f"{auth_service_url}/auth/session/me",
                cookies={'gustav_session': cookie},
                timeout=1.0  # Quick timeout for better UX
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Session valid for user: {data.get('user_id')}")
                logger.info(f"Session data: {data}")
                logger.info("=== FETCH SESSION FROM AUTH END (SUCCESS) ===")
                return data
            elif response.status_code == 401:
                logger.info("Session invalid or expired (401)")
                # Clear cache if session is invalid
                if 'user' in st.session_state:
                    logger.info("Deleting user from session_state")
                    del st.session_state.user
                logger.info("=== FETCH SESSION FROM AUTH END (401) ===")
                return None
            else:
                logger.warning(f"Unexpected status from auth service: {response.status_code}")
                logger.warning(f"Response body: {response.text[:200]}")
                logger.info("=== FETCH SESSION FROM AUTH END (ERROR) ===")
                return None
                
        except requests.Timeout:
            logger.warning("Auth service timeout - using cached data if available")
            cached = st.session_state.get('user')
            logger.info(f"Cached user data: {'available' if cached else 'not available'}")
            logger.info("=== FETCH SESSION FROM AUTH END (TIMEOUT) ===")
            return cached
        except Exception as e:
            logger.error(f"Auth service error: {str(e)}", exc_info=True)
            logger.info("=== FETCH SESSION FROM AUTH END (EXCEPTION) ===")
            return None
    
    @staticmethod
    def get_current_user() -> Optional[Dict[str, Any]]:
        """Get current user with intelligent caching and request coalescing."""
        logger.info("=== GET CURRENT USER START ===")
        
        # 0. Check if cookie exists - if not, invalidate cache
        cookie = None
        if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
            all_cookies = dict(st.context.cookies)
            logger.info(f"Available cookies in get_current_user: {list(all_cookies.keys())}")
            cookie = st.context.cookies.get('gustav_session')
            if cookie:
                logger.info(f"Found gustav_session: {cookie[:16]}...")
        else:
            logger.warning("st.context.cookies not available in get_current_user")
        
        if not cookie:
            # No cookie = user logged out, clear cache
            logger.info("No session cookie found, clearing cache")
            AuthSession.invalidate_cache()
            logger.info("=== GET CURRENT USER END (NO COOKIE) ===")
            return None
        
        # 1. Check cache only if cookie exists
        if 'user' in st.session_state and 'user_cache_time' in st.session_state:
            cache_age = datetime.now() - st.session_state.user_cache_time
            logger.info(f"Cache age: {cache_age.total_seconds():.1f}s, max: {AuthSession.CACHE_DURATION.total_seconds()}s")
            if cache_age < AuthSession.CACHE_DURATION:
                logger.info(f"Using cached user data: {st.session_state.user.get('email')}")
                logger.info("=== GET CURRENT USER END (CACHED) ===")
                return st.session_state.user
        
        # 2. Legacy fallback - check nginx headers (remove after full migration)
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            headers = dict(st.context.headers)
            user_id = headers.get('x-user-id') or headers.get('X-User-Id')
            if user_id:
                logger.info("Using legacy nginx headers (migration pending)")
                user_data = {
                    'id': user_id,
                    'email': headers.get('x-user-email') or headers.get('X-User-Email'),
                    'role': headers.get('x-user-role') or headers.get('X-User-Role'),
                }
                st.session_state.user = user_data
                st.session_state.user_cache_time = datetime.now()
                return user_data
        
        # 3. Fetch from auth service with request coalescing
        with AuthSession._fetch_lock:
            # Check if another thread already fetched while we were waiting
            if 'user' in st.session_state and 'user_cache_time' in st.session_state:
                cache_age = datetime.now() - st.session_state.user_cache_time
                if cache_age < timedelta(seconds=1):  # Very recent fetch
                    logger.debug("Using data fetched by another thread")
                    return st.session_state.user
            
            # Perform the fetch
            user_data = AuthSession._fetch_session_from_auth()
            
            if user_data:
                # Transform the response to match expected format
                transformed_data = {
                    'id': user_data.get('user_id'),
                    'email': user_data.get('email'),
                    'role': user_data.get('role'),
                    'expires_at': user_data.get('expires_at'),
                    'metadata': user_data.get('metadata', {})
                }
                
                st.session_state.user = transformed_data
                st.session_state.user_cache_time = datetime.now()
                st.session_state.role = user_data.get('role')
                return transformed_data
        
        # Clear stale cache if fetch failed
        for key in ['user', 'user_cache_time', 'role']:
            if key in st.session_state:
                del st.session_state[key]
        
        return None
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is currently authenticated."""
        return AuthSession.get_current_user() is not None
    
    @staticmethod
    def validate_session() -> bool:
        """Lightweight session validation check."""
        cookie = None
        
        if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
            cookie = st.context.cookies.get('gustav_session')
        
        if not cookie:
            return False
        
        # Quick check if we have valid cached data
        if 'user' in st.session_state and 'user_cache_time' in st.session_state:
            cache_age = datetime.now() - st.session_state.user_cache_time
            if cache_age < AuthSession.CACHE_DURATION:
                return True
        
        auth_service_url = AuthSession.get_auth_service_url()
        
        try:
            response = requests.get(
                f"{auth_service_url}/auth/session/validate",
                cookies={'gustav_session': cookie},
                timeout=0.5  # Very quick timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                is_valid = data.get('valid', False)
                
                # Update validation timestamp if valid
                if is_valid:
                    st.session_state.last_validation = datetime.now()
                
                return is_valid
        except:
            # On error, assume valid to prevent lockouts
            return True
        
        return False
    
    @staticmethod
    def invalidate_cache():
        """Force cache invalidation."""
        logger.info("=== CACHE INVALIDATION START ===")
        cleared_keys = []
        for key in ['user', 'user_cache_time', 'role', 'last_validation']:
            if key in st.session_state:
                logger.info(f"Deleting session_state.{key}")
                del st.session_state[key]
                cleared_keys.append(key)
        logger.info(f"Cleared keys: {cleared_keys}")
        logger.info("=== CACHE INVALIDATION END ===")
    
    @staticmethod
    def requires_revalidation() -> bool:
        """Check if session needs revalidation."""
        if 'last_validation' not in st.session_state:
            return True
        
        age = datetime.now() - st.session_state.last_validation
        return age > timedelta(minutes=5)
    
    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        """Login via FastAPI auth service."""
        try:
            auth_url = urljoin(AuthSession.get_auth_service_url(), "/auth/login")
            
            response = requests.post(
                auth_url,
                json={"email": email, "password": password},
                timeout=30,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Login successful for user: {email}")
                
                # Invalidate cache to force fresh fetch
                AuthSession.invalidate_cache()
                
                return result
            else:
                error_detail = "Login failed"
                try:
                    error_response = response.json()
                    error_detail = error_response.get("detail", error_detail)
                except Exception:
                    error_detail = f"HTTP {response.status_code}: {response.text[:100]}"
                
                logger.warning(f"Login failed for {email}: {error_detail}")
                raise Exception(error_detail)
                
        except requests.RequestException as e:
            logger.error(f"Network error during login: {e}")
            raise Exception(f"Verbindungsfehler zum Auth Service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}")
            raise
    
    @staticmethod
    def logout() -> None:
        """Logout via FastAPI auth service."""
        try:
            auth_url = urljoin(AuthSession.get_auth_service_url(), "/auth/logout")
            
            # Get session cookie if available
            cookies = {}
            if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
                gustav_session = st.context.cookies.get("gustav_session")
                if gustav_session:
                    cookies["gustav_session"] = gustav_session
            
            response = requests.post(
                auth_url,
                cookies=cookies,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Logout successful")
                
                # Clear all cached data
                AuthSession.invalidate_cache()
            else:
                error_detail = f"HTTP {response.status_code}: {response.text[:100]}"
                logger.warning(f"Logout failed: {error_detail}")
                raise Exception(f"Logout fehlgeschlagen: {error_detail}")
                
        except requests.RequestException as e:
            logger.error(f"Network error during logout: {e}")
            raise Exception(f"Verbindungsfehler zum Auth Service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during logout: {e}")
            raise
    
    @staticmethod
    def requires_login() -> bool:
        """Check if current page requires authentication."""
        if not AuthSession.is_authenticated():
            # Allow access to main page (which has login form)
            try:
                import inspect
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    filename = frame.f_back.f_code.co_filename
                    if 'main.py' in filename:
                        return True
            except Exception:
                pass
            
            st.warning("🔒 Bitte melden Sie sich an, um auf diese Seite zuzugreifen.")
            st.info("Gehen Sie zur [Startseite](/) um sich anzumelden.")
            st.stop()
            return False
        
        return True
    
    @staticmethod
    def sync_session_state() -> None:
        """Synchronize auth data with Streamlit session state."""
        user = AuthSession.get_current_user()
        
        if user:
            # Update session state with current user info
            # Keep as dict - AuthIntegration will wrap it in SecureUserDict
            st.session_state.user = user
            st.session_state.role = user.get('role')
            
            # Create a minimal session object for compatibility
            if 'session' not in st.session_state:
                st.session_state.session = {
                    'user': {
                        'id': user.get('id'),
                        'email': user.get('email')
                    }
                }
        else:
            # Clear session state if no user
            AuthSession.invalidate_cache()
    
    @staticmethod
    def get_development_fallback() -> bool:
        """Check if we should use development fallback mode."""
        return os.getenv("ENVIRONMENT") == "development"
    
    @staticmethod
    def handle_auth_failure() -> Optional[Dict[str, Any]]:
        """Handle auth service failures gracefully."""
        fallback_mode = os.getenv('AUTH_FALLBACK_MODE', 'cached')
        
        if fallback_mode == 'strict':
            # No access without auth service
            return None
        
        elif fallback_mode == 'cached':
            # Use last known good state
            cached = st.session_state.get('user')
            if cached:
                logger.warning("Using cached auth data due to service failure")
                # Extend cache by 10 minutes during outage
                st.session_state.user_cache_time = datetime.now()
            return cached
        
        elif fallback_mode == 'readonly':
            # Emergency read-only mode
            logger.warning("Auth service down - readonly mode")
            return {
                'id': 'emergency-readonly',
                'email': 'readonly@system',
                'role': 'readonly'
            }
        
        return None


# Convenience functions for backward compatibility
def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current authenticated user."""
    return AuthSession.get_current_user()

def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return AuthSession.is_authenticated()

def requires_login() -> bool:
    """Require authentication for current page."""
    return AuthSession.requires_login()