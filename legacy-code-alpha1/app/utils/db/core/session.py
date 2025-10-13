"""
Session management and RPC helper functions for HttpOnly cookie support.
This module contains the core session handling logic for database operations.
"""

import streamlit as st
from typing import Optional
from ...session_client import get_anon_supabase_client


def get_session_id() -> Optional[str]:
    """Get session ID from HttpOnly cookie.
    
    Returns:
        Optional[str]: Session ID if found, None otherwise
    """
    if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
        return st.context.cookies.get("gustav_session")
    return None


def get_anon_client():
    """Get anonymous Supabase client for RPC calls.
    
    Returns:
        Supabase client instance configured for anonymous access
    """
    return get_anon_supabase_client()


def handle_rpc_result(result, default_value=None):
    """Unified RPC error handling.
    
    Args:
        result: Supabase RPC execution result
        default_value: Default value to return on error (default: None)
        
    Returns:
        tuple: (data, error_message)
            - data: Result data or default_value on error
            - error_message: Error message string or None if successful
    """
    if hasattr(result, 'error') and result.error:
        error_msg = result.error.get('message', 'Database error')
        return default_value or [], f"Error: {error_msg}"
    return result.data or default_value or [], None