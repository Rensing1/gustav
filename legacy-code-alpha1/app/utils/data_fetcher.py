"""
Data Fetcher for GUSTAV
Fetches data through Auth Service proxy endpoints when using HttpOnly cookies
"""
import requests
from typing import List, Dict, Any, Optional
import streamlit as st
import logging
from urllib.parse import urljoin
import os
from .cookie_utils import get_session_cookie

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Fetches data through Auth Service proxy endpoints using HttpOnly cookies
    """
    
    def __init__(self):
        self.auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth:8000')
    
    
    def _make_proxy_request(self, endpoint: str) -> Dict[str, Any]:
        """Make authenticated request through auth service proxy"""
        logger.info(f"=== PROXY REQUEST START: {endpoint} ===")
        
        session_id = get_session_cookie()
        if not session_id:
            logger.error("No session cookie available for proxy request")
            logger.info(f"=== PROXY REQUEST END: {endpoint} (NO COOKIE) ===")
            return {"error": "No session", "data": []}
        
        logger.info(f"Using session cookie: {session_id[:16]}...")
        # The data_proxy router is mounted at /auth/api
        url = urljoin(self.auth_service_url, f"/auth/api{endpoint}")
        logger.info(f"Proxy URL: {url}")
        
        try:
            logger.debug(f"Making GET request to {url}")
            response = requests.get(
                url,
                cookies={"gustav_session": session_id},
                timeout=10
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 401:
                logger.warning(f"Unauthorized request to {endpoint}")
                logger.info(f"=== PROXY REQUEST END: {endpoint} (401 UNAUTHORIZED) ===")
                return {"error": "Unauthorized", "data": []}
            
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched {len(data) if isinstance(data, list) else 'object'} items")
            logger.info(f"=== PROXY REQUEST END: {endpoint} (SUCCESS) ===")
            return {"data": data, "error": None}
            
        except requests.RequestException as e:
            logger.error(f"Proxy request failed: {e}", exc_info=True)
            logger.info(f"=== PROXY REQUEST END: {endpoint} (ERROR) ===")
            return {"error": str(e), "data": []}
    
    def get_courses(self) -> List[Dict[str, Any]]:
        """Get courses for the current user"""
        result = self._make_proxy_request("/courses")
        return result.get("data", [])
    
    def get_course_units(self, course_id: str) -> List[Dict[str, Any]]:
        """Get learning units for a specific course"""
        result = self._make_proxy_request(f"/courses/{course_id}/units")
        return result.get("data", [])
    
    def get_user_progress(self) -> Dict[str, Any]:
        """Get user progress data"""
        result = self._make_proxy_request("/user/progress")
        return result.get("data", {"progress": {}})
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile data"""
        result = self._make_proxy_request("/user/profile")
        return result.get("data", {})


# Singleton instance
data_fetcher = DataFetcher()