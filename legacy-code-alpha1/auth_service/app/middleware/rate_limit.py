# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Rate limiting middleware for GUSTAV Auth Service
Implements enhanced security with 3/min + 10/hour limits
"""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis
from typing import Optional
import logging
from datetime import datetime, timedelta
import json

from ..config import settings

logger = logging.getLogger(__name__)

# Create Redis client for rate limiting
redis_client = redis.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
    decode_responses=True
)


class EnhancedRateLimiter:
    """Enhanced rate limiter with account lockout capabilities"""
    
    def __init__(self):
        self.limiter = Limiter(
            key_func=self._get_identifier,
            storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"
        )
    
    def _get_identifier(self, request: Request) -> str:
        """Get identifier for rate limiting (IP + email if available)"""
        client_ip = get_remote_address(request)
        
        # For login attempts, also track by email
        if request.url.path == "/auth/login" and request.method == "POST":
            # Try to get email from form data (this is async, handled separately)
            return f"login:{client_ip}"
        
        return client_ip
    
    async def check_account_lockout(self, email: str) -> bool:
        """Check if account is locked out"""
        lockout_key = f"lockout:{email}"
        lockout_data = await redis_client.get(lockout_key)
        
        if lockout_data:
            lockout_info = json.loads(lockout_data)
            lockout_until = datetime.fromisoformat(lockout_info["locked_until"])
            
            if datetime.utcnow() < lockout_until:
                logger.warning(f"Account locked out", extra={
                    "email": email,
                    "locked_until": lockout_until.isoformat(),
                    "attempts": lockout_info.get("attempts", 0)
                })
                return True
            else:
                # Lockout expired, remove it
                await redis_client.delete(lockout_key)
        
        return False
    
    async def record_failed_attempt(self, email: str, client_ip: str):
        """Record failed login attempt and check for lockout"""
        # Track attempts by email
        attempt_key = f"attempts:{email}"
        hourly_key = f"attempts:hourly:{email}"
        
        # Increment counters
        await redis_client.incr(attempt_key)
        await redis_client.expire(attempt_key, 60)  # 1 minute window
        
        await redis_client.incr(hourly_key)
        await redis_client.expire(hourly_key, 3600)  # 1 hour window
        
        # Check limits
        minute_attempts = await redis_client.get(attempt_key)
        hour_attempts = await redis_client.get(hourly_key)
        
        minute_attempts = int(minute_attempts) if minute_attempts else 0
        hour_attempts = int(hour_attempts) if hour_attempts else 0
        
        # Apply lockout if limits exceeded
        if minute_attempts > 3 or hour_attempts > 10:
            lockout_duration = timedelta(hours=1)
            lockout_until = datetime.utcnow() + lockout_duration
            
            lockout_data = {
                "locked_until": lockout_until.isoformat(),
                "attempts": hour_attempts,
                "locked_at": datetime.utcnow().isoformat(),
                "ip_address": client_ip
            }
            
            await redis_client.set(
                f"lockout:{email}",
                json.dumps(lockout_data),
                ex=int(lockout_duration.total_seconds())
            )
            
            logger.warning(f"Account locked due to too many attempts", extra={
                "email": email,
                "minute_attempts": minute_attempts,
                "hour_attempts": hour_attempts,
                "lockout_until": lockout_until.isoformat()
            })
            
            return True
        
        return False
    
    async def clear_attempts(self, email: str):
        """Clear failed attempts after successful login"""
        await redis_client.delete(f"attempts:{email}")
        await redis_client.delete(f"attempts:hourly:{email}")
        await redis_client.delete(f"lockout:{email}")


# Global rate limiter instance
rate_limiter = EnhancedRateLimiter()


# Rate limit decorators for different endpoints
login_limiter = rate_limiter.limiter.limit("3/minute")
api_limiter = rate_limiter.limiter.limit("30/minute")
verify_limiter = rate_limiter.limiter.limit("100/minute")  # Higher for auth checks


# Custom error handler for rate limits
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded"""
    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Zu viele Anfragen. Bitte versuchen Sie es später erneut.",
            "error": "rate_limit_exceeded"
        }
    )
    response.headers["Retry-After"] = str(exc.retry_after)
    response.headers["X-RateLimit-Limit"] = str(exc.limit)
    response.headers["X-RateLimit-Remaining"] = "0"
    response.headers["X-RateLimit-Reset"] = str(int(exc.reset))
    
    return response