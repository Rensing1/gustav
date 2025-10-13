"""
Supabase Authentication Proxy
Reuses original session tokens from login to make authenticated requests
"""
from supabase import create_client, Client
from typing import Dict, Any, Optional
import structlog
import json

from ..config import settings

logger = structlog.get_logger()


class SupabaseAuthProxy:
    """
    Proxy that reuses the original Supabase session for authenticated requests.
    This avoids the need for a service role key by using the user's actual session.
    """
    
    def __init__(self):
        self._client_cache: Dict[str, Client] = {}
    
    async def get_authenticated_client(self, session_data: Dict[str, Any]) -> Client:
        """
        Get a Supabase client authenticated with the user's original session.
        
        Args:
            session_data: Session data from auth_sessions table containing:
                - data: JSON field with original access_token and refresh_token
                - user_id: User ID for this session
                
        Returns:
            Authenticated Supabase client
        """
        # Extract original tokens from session data
        logger.debug(f"Session data keys: {list(session_data.keys())}")
        logger.debug(f"Session data type: {type(session_data)}")
        
        session_info = session_data.get("data", {})
        logger.debug(f"Session info type: {type(session_info)}, value: {session_info}")
        
        if isinstance(session_info, str):
            try:
                session_info = json.loads(session_info)
                logger.debug(f"Parsed JSON session info: {list(session_info.keys()) if isinstance(session_info, dict) else 'not a dict'}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse session data as JSON: {e}")
                session_info = {}
        
        access_token = session_info.get("access_token")
        refresh_token = session_info.get("refresh_token")
        
        logger.debug(f"Access token found: {bool(access_token)}")
        logger.debug(f"Refresh token found: {bool(refresh_token)}")
        
        if not access_token:
            logger.error("no_access_token_in_session", 
                        user_id=session_data.get("user_id"),
                        session_data_keys=list(session_data.keys()),
                        session_info_keys=list(session_info.keys()) if isinstance(session_info, dict) else "not a dict")
            raise ValueError("No access token found in session")
        
        # Create cache key from user_id (not token for security)
        cache_key = f"user_{session_data.get('user_id')}"
        
        # Check if we have a cached client
        if cache_key in self._client_cache:
            cached_client = self._client_cache[cache_key]
            # Verify the client is still valid by checking auth
            try:
                user = cached_client.auth.get_user(access_token)
                if user:
                    logger.debug("reusing_cached_client", user_id=session_data.get("user_id"))
                    return cached_client
            except:
                # Client is invalid, remove from cache
                del self._client_cache[cache_key]
        
        # Create new authenticated client
        client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )
        
        # Set the session on the client
        try:
            # Use set_session to authenticate the client
            client.auth.set_session(access_token, refresh_token)
            
            # Verify the session works
            user = client.auth.get_user()
            if not user:
                raise ValueError("Failed to authenticate client")
            
            logger.info("authenticated_client_created", 
                       user_id=session_data.get("user_id"))
            
            # Cache the client for future requests
            self._client_cache[cache_key] = client
            
            # Limit cache size
            if len(self._client_cache) > 100:
                # Remove oldest entries
                oldest_key = list(self._client_cache.keys())[0]
                del self._client_cache[oldest_key]
            
            return client
            
        except Exception as e:
            logger.error("client_authentication_failed", 
                        error=str(e),
                        user_id=session_data.get("user_id"))
            raise ValueError(f"Failed to authenticate Supabase client: {str(e)}")
    
    def clear_cache(self, user_id: Optional[str] = None):
        """
        Clear cached clients.
        
        Args:
            user_id: If provided, only clear cache for this user
        """
        if user_id:
            cache_key = f"user_{user_id}"
            if cache_key in self._client_cache:
                del self._client_cache[cache_key]
                logger.info("client_cache_cleared", user_id=user_id)
        else:
            self._client_cache.clear()
            logger.info("all_client_cache_cleared")