"""Platform-related database functions for HttpOnly Cookie support.

This package contains all platform-related functions for feedback
that have been migrated to use the RPC pattern with session-based 
authentication.
"""

from .feedback import submit_feedback, get_all_feedback

__all__ = ['submit_feedback', 'get_all_feedback']