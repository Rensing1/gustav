"""
Redis connection manager with connection pooling
Handles session storage for auth service
"""
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional, Dict, Any
import json
import structlog
from contextlib import asynccontextmanager

from app.config import settings

logger = structlog.get_logger()


class RedisManager:
    """Manages Redis connections with pooling and error handling"""
    
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        if self._initialized:
            return
            
        try:
            # Use direct connection instead of pool for now
            # uvloop has issues with some socket options in connection pools
            self.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )
            
            # Test connection
            await self.client.ping()
            
            self._initialized = True
            logger.info("redis_initialized", 
                       url=settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL)
            
        except Exception as e:
            logger.error("redis_initialization_failed", error=str(e))
            raise
    
    async def close(self):
        """Close Redis connections"""
        if self.client:
            await self.client.aclose()  # Use aclose() for async client
        self._initialized = False
        logger.info("redis_connection_closed")
    
    @asynccontextmanager
    async def session_lock(self, session_id: str, timeout: int = 5):
        """
        Context manager for session locking to prevent race conditions
        """
        lock_key = f"lock:session:{session_id}"
        lock_acquired = False
        
        try:
            # Try to acquire lock with timeout
            lock_acquired = await self.client.set(
                lock_key, "1", ex=timeout, nx=True
            )
            
            if not lock_acquired:
                raise ValueError(f"Could not acquire lock for session {session_id}")
            
            yield
            
        finally:
            if lock_acquired:
                await self.client.delete(lock_key)
    
    async def set_session(self, session_id: str, session_data: Dict[str, Any], 
                         ttl: int = None) -> bool:
        """
        Store session data in Redis
        
        Args:
            session_id: Unique session identifier
            session_data: Session data dictionary
            ttl: Time to live in seconds (default: SESSION_TIMEOUT_MINUTES)
        
        Returns:
            bool: Success status
        """
        if not self._initialized:
            raise RuntimeError("Redis not initialized")
        
        try:
            ttl = ttl or (settings.SESSION_TIMEOUT_MINUTES * 60)
            
            await self.client.setex(
                f"session:{session_id}",
                ttl,
                json.dumps(session_data)
            )
            
            # Track active sessions
            await self.client.sadd("active_sessions", session_id)
            
            return True
            
        except Exception as e:
            logger.error("redis_set_session_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data from Redis
        
        Args:
            session_id: Unique session identifier
        
        Returns:
            Session data dict or None if not found/expired
        """
        if not self._initialized:
            raise RuntimeError("Redis not initialized")
        
        try:
            data = await self.client.get(f"session:{session_id}")
            
            if data:
                # Update TTL on access (sliding expiration)
                await self.client.expire(
                    f"session:{session_id}", 
                    settings.SESSION_TIMEOUT_MINUTES * 60
                )
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error("redis_get_session_failed", 
                        session_id=session_id, 
                        error=str(e))
            return None
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session from Redis
        
        Args:
            session_id: Unique session identifier
        
        Returns:
            bool: Success status
        """
        if not self._initialized:
            raise RuntimeError("Redis not initialized")
        
        try:
            # Delete session data
            deleted = await self.client.delete(f"session:{session_id}")
            
            # Remove from active sessions
            await self.client.srem("active_sessions", session_id)
            
            return bool(deleted)
            
        except Exception as e:
            logger.error("redis_delete_session_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False
    
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update last activity timestamp for a session
        
        Args:
            session_id: Unique session identifier
        
        Returns:
            bool: Success status
        """
        try:
            session_data = await self.get_session(session_id)
            if not session_data:
                return False
            
            from datetime import datetime
            session_data["last_activity"] = datetime.utcnow().isoformat()
            
            return await self.set_session(session_id, session_data)
            
        except Exception as e:
            logger.error("redis_update_activity_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False
    
    async def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        if not self._initialized:
            return 0
        
        try:
            return await self.client.scard("active_sessions")
        except Exception:
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            if not self._initialized:
                return {"status": "not_initialized", "healthy": False}
            
            # Ping Redis
            await self.client.ping()
            
            return {
                "status": "healthy",
                "healthy": True,
                "active_sessions": await self.get_active_sessions_count()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "healthy": False,
                "error": str(e)
            }
    
    @property
    def pool_size(self) -> int:
        """Get configured max connections"""
        return settings.REDIS_MAX_CONNECTIONS


# Singleton instance
redis_manager = RedisManager()