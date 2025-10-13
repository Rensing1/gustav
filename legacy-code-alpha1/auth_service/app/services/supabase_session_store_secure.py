"""
Secure Supabase session storage using custom JWT with limited scope
This version creates a custom JWT that only has access to auth_sessions table
"""
import os
import jwt
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import secrets
import json
from cachetools import TTLCache
import structlog
from supabase import create_client, Client
from postgrest.exceptions import APIError

from app.config import settings

logger = structlog.get_logger()


class SecureSupabaseSessionStore:
    """
    Secure session storage using custom JWT with limited permissions.
    
    Instead of using the service role key directly, we create a custom JWT
    that only has the specific permissions needed for session management.
    """
    
    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 300, cache_size: int = 1000):
        """Initialize secure session store with custom JWT."""
        # Create a custom JWT with limited scope
        self.custom_jwt = self._create_session_management_jwt()
        
        # Initialize Supabase client with custom JWT
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            self.custom_jwt  # Use our custom JWT instead of service key
        )
        
        # Optional in-memory cache
        self.cache_enabled = cache_enabled
        if cache_enabled:
            self.cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
            logger.info("secure_session_store_initialized", 
                       cache_enabled=True, 
                       cache_ttl=cache_ttl, 
                       cache_size=cache_size)
        else:
            self.cache = None
            logger.info("secure_session_store_initialized", cache_enabled=False)
    
    def _create_session_management_jwt(self) -> str:
        """
        Create a custom JWT with limited permissions for session management.
        
        This JWT only allows:
        - INSERT/SELECT/UPDATE/DELETE on auth_sessions table
        - EXECUTE on session management functions
        """
        # JWT payload with specific role and permissions
        payload = {
            "role": "session_manager",  # Custom role we'll create in Supabase
            "iss": "supabase",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp()),
            "permissions": {
                "tables": {
                    "auth_sessions": ["SELECT", "INSERT", "UPDATE", "DELETE"]
                },
                "functions": [
                    "cleanup_expired_sessions",
                    "get_session_with_activity_update",
                    "enforce_session_limit"
                ]
            }
        }
        
        # Sign with Supabase JWT secret
        return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    def generate_session_id(self) -> str:
        """Generate cryptographically secure session ID."""
        return secrets.token_urlsafe(32)
    
    # ... rest of the methods remain the same as SupabaseSessionStore ...
    
    async def create_session(
        self, 
        user_id: str, 
        user_email: str, 
        user_role: str,
        data: Optional[Dict[str, Any]] = None,
        expires_in: int = 5400,  # 90 minutes default
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create a new session with limited JWT scope."""
        session_id = self.generate_session_id()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "user_email": user_email,
            "user_role": user_role,
            "data": data or {},
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        try:
            # Insert with limited scope JWT
            result = self.supabase.table("auth_sessions").insert(session_data).execute()
            
            logger.info("secure_session_created", 
                       session_id=session_id, 
                       user_id=user_id, 
                       role=user_role)
            
            if self.cache_enabled:
                self.cache[session_id] = result.data[0]
            
            return session_id
            
        except APIError as e:
            logger.error("secure_session_create_failed", 
                        user_id=user_id, 
                        error=str(e))
            raise Exception(f"Failed to create session: {str(e)}")