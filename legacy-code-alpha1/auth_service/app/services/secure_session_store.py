"""
Secure Supabase session storage using PostgreSQL functions with SECURITY DEFINER
No service role key required - uses only anon key!
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import structlog
from supabase import create_client, Client
from postgrest.exceptions import APIError

from app.config import settings

logger = structlog.get_logger()


class SecureSessionStore:
    """
    Session storage using secure PostgreSQL functions.
    This implementation doesn't need service role key - only anon key.
    """
    
    def __init__(self):
        """Initialize with anon key only - no service role needed!"""
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY  # Only anon key needed!
        )
        logger.info("secure_session_store_initialized", 
                   backend="postgresql_functions",
                   security="SECURITY_DEFINER")
    
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
        """Create a new session using secure function."""
        try:
            # Convert seconds to PostgreSQL interval
            expires_interval = f"{expires_in} seconds"
            
            # Log the parameters for debugging
            logger.debug("create_session_params",
                        user_id=user_id,
                        user_email=user_email,
                        user_role=user_role,
                        data_type=type(data),
                        data_keys=list(data.keys()) if data else [],
                        expires_interval=expires_interval)
            
            result = self.supabase.rpc(
                "create_session_for_auth_service",
                {
                    "p_user_id": user_id,
                    "p_user_email": user_email,
                    "p_user_role": user_role,
                    "p_data": data or {},
                    "p_expires_in": expires_interval,
                    "p_ip_address": ip_address,
                    "p_user_agent": user_agent
                }
            ).execute()
            
            if result.data:
                # The new function returns session_id directly as a string
                session_id = result.data
                logger.info("session_created", 
                           user_id=user_id,
                           role=user_role,
                           session_id=session_id[:8] + "...")
                return session_id
            else:
                raise Exception("No session data returned")
                
        except APIError as e:
            logger.error("session_create_failed", 
                        user_id=user_id,
                        error=str(e.message),
                        code=e.code)
            
            # Handle specific errors
            if "User" in str(e.message) and "does not exist" in str(e.message):
                raise ValueError(f"User {user_id} does not exist")
            elif "Invalid user_role" in str(e.message):
                raise ValueError(f"Invalid role: {user_role}")
            else:
                raise Exception(f"Failed to create session: {str(e.message)}")
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session using secure function (also updates activity)."""
        try:
            result = self.supabase.rpc(
                "get_session",
                {"p_session_id": session_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except APIError as e:
            logger.error("session_get_failed",
                        session_id=session_id,
                        error=str(e))
            return None
    
    async def validate_session(self, session_id: str) -> Dict[str, Any]:
        """Validate session for nginx auth_request."""
        try:
            result = self.supabase.rpc(
                "validate_session",
                {"p_session_id": session_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return {
                "is_valid": False,
                "user_id": None,
                "user_email": None,
                "user_role": None,
                "expires_in_seconds": 0
            }
            
        except APIError as e:
            logger.error("session_validate_failed",
                        session_id=session_id,
                        error=str(e))
            return {
                "is_valid": False,
                "user_id": None,
                "user_email": None,
                "user_role": None,
                "expires_in_seconds": 0
            }
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data using secure function."""
        try:
            result = self.supabase.rpc(
                "update_session",
                {
                    "p_session_id": session_id,
                    "p_data": data
                }
            ).execute()
            
            return result.data[0] if result.data else False
            
        except APIError as e:
            logger.error("session_update_failed",
                        session_id=session_id,
                        error=str(e))
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session using secure function."""
        try:
            result = self.supabase.rpc(
                "delete_session",
                {"p_session_id": session_id}
            ).execute()
            
            # The SQL function returns a boolean directly
            success = result.data if isinstance(result.data, bool) else False
            if success:
                logger.info("session_deleted", session_id=session_id)
            return success
            
        except APIError as e:
            logger.error("session_delete_failed",
                        session_id=session_id,
                        error=str(e))
            return False
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        try:
            result = self.supabase.rpc(
                "get_user_sessions",
                {"p_user_id": user_id}
            ).execute()
            
            return result.data or []
            
        except APIError as e:
            logger.error("get_user_sessions_failed",
                        user_id=user_id,
                        error=str(e))
            return []
    
    async def invalidate_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        try:
            result = self.supabase.rpc(
                "invalidate_user_sessions",
                {"p_user_id": user_id}
            ).execute()
            
            count = result.data[0] if result.data else 0
            if count > 0:
                logger.info("user_sessions_invalidated",
                           user_id=user_id,
                           count=count)
            return count
            
        except APIError as e:
            logger.error("invalidate_user_sessions_failed",
                        user_id=user_id,
                        error=str(e))
            return 0
    
    async def refresh_session(self, session_id: str, extend_by: int = 5400) -> Optional[str]:
        """Refresh session expiration."""
        try:
            extend_interval = f"{extend_by} seconds"
            
            result = self.supabase.rpc(
                "refresh_session",
                {
                    "p_session_id": session_id,
                    "p_extend_by": extend_interval
                }
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]  # Returns new expires_at
            return None
            
        except APIError as e:
            logger.error("session_refresh_failed",
                        session_id=session_id,
                        error=str(e))
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if session functions are working."""
        try:
            # Try to validate a non-existent session
            result = await self.validate_session("health-check-session")
            
            return {
                "healthy": True,
                "backend": "postgresql_functions",
                "security": "SECURITY_DEFINER",
                "service_key_required": False
            }
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup is handled automatically by PostgreSQL.
        This method exists for API compatibility.
        """
        # The cleanup_expired_sessions function is called periodically by PostgreSQL
        logger.info("cleanup_triggered", 
                   note="Handled automatically by PostgreSQL scheduler")
        return 0