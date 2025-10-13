"""Core database functionality for HttpOnly Cookie support.

This package contains fundamental database access patterns including
session management and authentication/authorization functions.
"""

# Session management
from .session import (
    get_session_id,
    get_anon_client,
    handle_rpc_result
)

# Authentication and authorization
from .auth import (
    get_users_by_role,
    is_teacher_authorized_for_course
)

__all__ = [
    # Session management
    'get_session_id',
    'get_anon_client',
    'handle_rpc_result',
    # Authentication
    'get_users_by_role',
    'is_teacher_authorized_for_course',
]