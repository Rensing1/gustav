"""
Supabase-based session storage for GUSTAV auth service
Replaces Redis with PostgreSQL for pragmatic, simplified architecture
"""
import os
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


class SupabaseSessionStore:
    """
    Session storage using Supabase PostgreSQL instead of Redis.
    
    Features:
    - Session CRUD operations with PostgreSQL
    - Optional in-memory caching with TTLCache
    - Atomic session updates via stored procedures
    - Automatic session cleanup
    - Session limit enforcement (5 per user)
    """
    
    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 300, cache_size: int = 1000):
        """
        Initialize Supabase session store.
        
        Args:
            cache_enabled: Enable in-memory caching for performance
            cache_ttl: Cache TTL in seconds (default: 5 minutes)
            cache_size: Maximum number of cached sessions (default: 1000)
        """
        # Initialize Supabase client with service role key for full access
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # Service role key for auth_sessions access
        )
        
        # Optional in-memory cache for frequently accessed sessions
        self.cache_enabled = cache_enabled
        if cache_enabled:
            self.cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
            logger.info("session_store_initialized", 
                       cache_enabled=True, 
                       cache_ttl=cache_ttl, 
                       cache_size=cache_size)
        else:
            self.cache = None
            logger.info("session_store_initialized", cache_enabled=False)
    
    def generate_session_id(self) -> str:
        """Generate cryptographically secure session ID."""
        return secrets.token_urlsafe(32)
    
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
        """
        Create a new session in Supabase.
        
        Args:
            user_id: User UUID
            user_email: User email
            user_role: User role (teacher/student/admin)
            data: Additional session data
            expires_in: Expiration time in seconds
            ip_address: Client IP address
            user_agent: Browser user agent
            
        Returns:
            Session ID
        """
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
            # Insert session - trigger will handle session limit enforcement
            result = self.supabase.table("auth_sessions").insert(session_data).execute()
            
            logger.info("session_created", 
                       session_id=session_id, 
                       user_id=user_id, 
                       role=user_role,
                       expires_at=expires_at.isoformat())
            
            # Cache if enabled
            if self.cache_enabled:
                self.cache[session_id] = result.data[0]
            
            return session_id
            
        except APIError as e:
            logger.error("session_create_failed", 
                        user_id=user_id, 
                        error=str(e))
            raise Exception(f"Failed to create session: {str(e)}")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data with automatic activity update.
        Uses stored procedure for atomic read + activity update.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dict or None if not found/expired
        """
        # Check cache first
        if self.cache_enabled and session_id in self.cache:
            cached = self.cache[session_id]
            # Verify not expired
            if datetime.fromisoformat(cached['expires_at'].replace('Z', '+00:00')) > datetime.now(timezone.utc):
                logger.debug("session_cache_hit", session_id=session_id)
                return cached
        
        try:
            # Use stored procedure for atomic get + activity update
            result = self.supabase.rpc(
                'get_session_with_activity_update',
                {'p_session_id': session_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                session = result.data[0]
                
                # Update cache
                if self.cache_enabled:
                    self.cache[session_id] = session
                
                logger.debug("session_retrieved", session_id=session_id)
                return session
            
            logger.debug("session_not_found", session_id=session_id)
            return None
            
        except APIError as e:
            logger.error("session_get_failed", 
                        session_id=session_id, 
                        error=str(e))
            return None
    
    async def update_session(
        self, 
        session_id: str, 
        data: Dict[str, Any],
        extend_expiration: bool = True
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session identifier
            data: New session data (will be merged)
            extend_expiration: Whether to extend session expiration
            
        Returns:
            Success status
        """
        try:
            # Get current session
            current = await self.get_session(session_id)
            if not current:
                return False
            
            # Merge data
            merged_data = {**current.get('data', {}), **data}
            
            update_data = {
                "data": merged_data,
                "last_activity": datetime.now(timezone.utc).isoformat()
            }
            
            if extend_expiration:
                update_data["expires_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=5400)
                ).isoformat()
            
            # Update in database
            result = self.supabase.table("auth_sessions").update(update_data).eq(
                "session_id", session_id
            ).execute()
            
            # Update cache
            if self.cache_enabled and result.data:
                self.cache[session_id] = result.data[0]
            
            logger.debug("session_updated", session_id=session_id)
            return True
            
        except APIError as e:
            logger.error("session_update_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Success status
        """
        try:
            # Delete from database
            result = self.supabase.table("auth_sessions").delete().eq(
                "session_id", session_id
            ).execute()
            
            # Remove from cache
            if self.cache_enabled and session_id in self.cache:
                del self.cache[session_id]
            
            logger.info("session_deleted", session_id=session_id)
            return True
            
        except APIError as e:
            logger.error("session_delete_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions using stored procedure.
        
        Returns:
            Number of deleted sessions
        """
        try:
            result = self.supabase.rpc('cleanup_expired_sessions').execute()
            deleted_count = result.data or 0
            
            if deleted_count > 0:
                logger.info("expired_sessions_cleaned", count=deleted_count)
                
                # Clear cache to avoid serving expired sessions
                if self.cache_enabled:
                    self.cache.clear()
            
            return deleted_count
            
        except APIError as e:
            logger.error("session_cleanup_failed", error=str(e))
            return 0
    
    async def get_user_sessions(self, user_id: str) -> list[Dict[str, Any]]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of active sessions
        """
        try:
            result = self.supabase.table("auth_sessions").select("*").eq(
                "user_id", user_id
            ).gt("expires_at", datetime.now(timezone.utc).isoformat()).execute()
            
            return result.data or []
            
        except APIError as e:
            logger.error("user_sessions_get_failed", 
                        user_id=user_id, 
                        error=str(e))
            return []
    
    async def invalidate_user_sessions(self, user_id: str) -> int:
        """
        Invalidate all sessions for a user (e.g., on password change).
        
        Args:
            user_id: User UUID
            
        Returns:
            Number of invalidated sessions
        """
        try:
            # Get all user sessions
            sessions = await self.get_user_sessions(user_id)
            
            # Delete all sessions
            if sessions:
                session_ids = [s['session_id'] for s in sessions]
                result = self.supabase.table("auth_sessions").delete().in_(
                    "session_id", session_ids
                ).execute()
                
                # Clear from cache
                if self.cache_enabled:
                    for sid in session_ids:
                        self.cache.pop(sid, None)
                
                logger.info("user_sessions_invalidated", 
                           user_id=user_id, 
                           count=len(sessions))
                
            return len(sessions)
            
        except APIError as e:
            logger.error("user_sessions_invalidate_failed", 
                        user_id=user_id, 
                        error=str(e))
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check session store health.
        
        Returns:
            Health status dict
        """
        try:
            # Try to count sessions
            result = self.supabase.table("auth_sessions").select(
                "count", count="exact"
            ).execute()
            
            active_count = result.count or 0
            
            return {
                "status": "healthy",
                "healthy": True,
                "active_sessions": active_count,
                "cache_enabled": self.cache_enabled,
                "cache_size": len(self.cache) if self.cache_enabled else 0
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "healthy": False,
                "error": str(e)
            }
    
    def clear_cache(self):
        """Clear the in-memory cache."""
        if self.cache_enabled:
            self.cache.clear()
            logger.info("session_cache_cleared")


# Singleton instance
session_store = SupabaseSessionStore()