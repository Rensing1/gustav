# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Security utilities for GUSTAV.

Provides functions for secure logging, PII hashing, and other security-related operations.
"""

import hashlib
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def hash_id(value: str) -> str:
    """Hash sensitive IDs für Logging.
    
    Args:
        value: The sensitive value to hash
        
    Returns:
        First 8 characters of the SHA256 hash, or "NONE" if value is empty
    """
    if not value:
        return "NONE"
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def security_log(message: str, **kwargs: Dict[str, Any]) -> None:
    """Log mit automatischem PII-Hashing.
    
    Automatically hashes sensitive fields like user_id, student_id, email, etc.
    before logging to prevent PII exposure.
    
    Args:
        message: The log message
        **kwargs: Additional fields to log (sensitive fields will be hashed)
    """
    sensitive_fields = ['user_id', 'student_id', 'email', 'course_id', 'teacher_id']
    
    # Create a copy of kwargs to avoid modifying the original
    safe_kwargs = kwargs.copy()
    
    # Hash sensitive fields
    for field in sensitive_fields:
        if field in safe_kwargs:
            safe_kwargs[f"{field}_hash"] = hash_id(str(safe_kwargs[field]))
            del safe_kwargs[field]
    
    logger.info(message, extra=safe_kwargs)


def hash_ip(ip_address: str) -> str:
    """Hash IP addresses for privacy.
    
    Args:
        ip_address: The IP address to hash
        
    Returns:
        First 8 characters of the SHA256 hash
    """
    if not ip_address:
        return "NONE"
    return hashlib.sha256(ip_address.encode()).hexdigest()[:8]


def get_safe_error_message(error: Exception, user_facing: bool = True) -> str:
    """Get a safe error message without exposing sensitive details.
    
    Args:
        error: The exception that occurred
        user_facing: If True, returns generic message. If False, includes more details
        
    Returns:
        A safe error message string
    """
    if user_facing:
        # Generic messages for users
        error_messages = {
            "IntegrityError": "Ein Eintrag mit diesen Daten existiert bereits.",
            "PermissionError": "Sie haben keine Berechtigung für diese Aktion.",
            "ValidationError": "Die eingegebenen Daten sind ungültig.",
            "ConnectionError": "Verbindungsfehler. Bitte versuchen Sie es später erneut.",
        }
        
        error_type = type(error).__name__
        return error_messages.get(error_type, "Ein unerwarteter Fehler ist aufgetreten.")
    else:
        # More detailed message for logging (but still no PII)
        return f"{type(error).__name__}: {str(error)}"