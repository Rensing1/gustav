# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Rate limiting utilities for GUSTAV.

Provides in-memory rate limiting for file uploads to prevent API bypass attacks.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Tuple, List

from .security import security_log


# Global in-memory storage for upload tracking
# Structure: user_id -> [(timestamp, file_size), ...]
_upload_history = defaultdict(list)

# Rate limiting configuration
MAX_UPLOADS_PER_HOUR = 10
MAX_SIZE_PER_HOUR = 50 * 1024 * 1024  # 50MB


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


def check_upload_rate_limit(user_id: str, file_size: int) -> None:
    """
    Check if upload is within rate limits.
    
    Args:
        user_id: The user ID to check rate limits for
        file_size: Size of the file being uploaded in bytes
        
    Raises:
        RateLimitExceeded: If rate limit would be exceeded
    """
    if not user_id:
        raise ValueError("user_id cannot be empty")
    
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    
    # Get user's upload history
    user_uploads = _upload_history[user_id]
    
    # Filter uploads from the last hour
    recent_uploads = [
        (timestamp, size) for timestamp, size in user_uploads
        if timestamp > hour_ago
    ]
    
    # Check upload count limit
    if len(recent_uploads) >= MAX_UPLOADS_PER_HOUR:
        security_log(
            "Rate limit exceeded: too many uploads",
            user_id=user_id,
            upload_count=len(recent_uploads),
            max_uploads=MAX_UPLOADS_PER_HOUR,
            time_window="1h"
        )
        raise RateLimitExceeded(f"Maximal {MAX_UPLOADS_PER_HOUR} Uploads pro Stunde erlaubt")
    
    # Check total size limit
    total_size = sum(size for _, size in recent_uploads) + file_size
    if total_size > MAX_SIZE_PER_HOUR:
        security_log(
            "Rate limit exceeded: total size too large",
            user_id=user_id,
            total_size_mb=total_size // 1024 // 1024,
            max_size_mb=MAX_SIZE_PER_HOUR // 1024 // 1024,
            time_window="1h"
        )
        raise RateLimitExceeded(f"Maximal {MAX_SIZE_PER_HOUR // 1024 // 1024}MB pro Stunde erlaubt")
    
    # Record the upload
    user_uploads.append((now, file_size))
    
    security_log(
        "Upload rate check passed",
        user_id=user_id,
        file_size_mb=file_size // 1024 // 1024 if file_size > 1024 * 1024 else 0,
        uploads_in_hour=len(recent_uploads) + 1,
        total_size_hour_mb=total_size // 1024 // 1024
    )


def get_upload_stats(user_id: str) -> dict:
    """
    Get current upload statistics for a user.
    
    Args:
        user_id: The user ID to get stats for
        
    Returns:
        Dictionary with upload statistics
    """
    if not user_id:
        return {"uploads_last_hour": 0, "size_last_hour_mb": 0}
    
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    
    user_uploads = _upload_history[user_id]
    recent_uploads = [
        (timestamp, size) for timestamp, size in user_uploads
        if timestamp > hour_ago
    ]
    
    total_size = sum(size for _, size in recent_uploads)
    
    return {
        "uploads_last_hour": len(recent_uploads),
        "size_last_hour_mb": total_size // 1024 // 1024,
        "remaining_uploads": max(0, MAX_UPLOADS_PER_HOUR - len(recent_uploads)),
        "remaining_size_mb": max(0, (MAX_SIZE_PER_HOUR - total_size) // 1024 // 1024)
    }


def get_rate_limit_info() -> dict:
    """
    Get information about current rate limits.
    
    Returns:
        Dictionary with rate limit configuration
    """
    return {
        "max_uploads_per_hour": MAX_UPLOADS_PER_HOUR,
        "max_size_per_hour_mb": MAX_SIZE_PER_HOUR // 1024 // 1024,
        "time_window_hours": 1
    }