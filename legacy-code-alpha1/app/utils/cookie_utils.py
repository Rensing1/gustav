"""
Cookie Utilities for GUSTAV
Provides consistent cookie access across the application
"""
import streamlit as st
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def get_cookie(cookie_name: str) -> Optional[str]:
    """
    Get a cookie value from the current request context.
    
    Args:
        cookie_name: Name of the cookie to retrieve
        
    Returns:
        Cookie value if found, None otherwise
    """
    logger.info(f"=== GET COOKIE '{cookie_name}' START ===")
    
    # Method 1: Try st.context.cookies (preferred in newer Streamlit versions)
    if hasattr(st, 'context') and hasattr(st.context, 'cookies'):
        logger.debug("Checking st.context.cookies")
        all_cookies = dict(st.context.cookies) if st.context.cookies else {}
        logger.debug(f"Available cookies via st.context.cookies: {list(all_cookies.keys())}")
        
        cookie_value = st.context.cookies.get(cookie_name)
        if cookie_value:
            logger.info(f"Found {cookie_name} via st.context.cookies: {cookie_value[:16]}...")
            logger.info(f"=== GET COOKIE '{cookie_name}' END (FOUND via context.cookies) ===")
            return cookie_value
    else:
        logger.debug("st.context.cookies not available")
    
    # Method 2: Fallback to parsing Cookie header
    if hasattr(st, 'context') and hasattr(st.context, 'headers'):
        logger.debug("Checking Cookie header")
        headers = dict(st.context.headers)
        cookie_header = headers.get('cookie', '') or headers.get('Cookie', '')
        
        if cookie_header:
            logger.debug(f"Raw Cookie header: {cookie_header[:100]}...")
            # Parse cookies from header
            cookies = parse_cookie_header(cookie_header)
            logger.debug(f"Parsed cookies: {list(cookies.keys())}")
            
            cookie_value = cookies.get(cookie_name)
            if cookie_value:
                logger.info(f"Found {cookie_name} via Cookie header: {cookie_value[:16]}...")
                logger.info(f"=== GET COOKIE '{cookie_name}' END (FOUND via header) ===")
                return cookie_value
            else:
                logger.warning(f"{cookie_name} not found. Available cookies: {list(cookies.keys())}")
        else:
            logger.debug("No Cookie header found")
    else:
        logger.debug("st.context.headers not available")
    
    logger.warning(f"Cookie {cookie_name} not found in request context")
    logger.info(f"=== GET COOKIE '{cookie_name}' END (NOT FOUND) ===")
    return None


def parse_cookie_header(cookie_header: str) -> Dict[str, str]:
    """
    Parse a Cookie header string into a dictionary.
    
    Args:
        cookie_header: Raw Cookie header value
        
    Returns:
        Dictionary of cookie names to values
    """
    cookies = {}
    for cookie in cookie_header.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def get_session_cookie() -> Optional[str]:
    """
    Get the GUSTAV session cookie from the current request.
    
    Returns:
        Session cookie value if found, None otherwise
    """
    return get_cookie('gustav_session')