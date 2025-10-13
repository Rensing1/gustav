"""
Data Proxy Routes for GUSTAV Auth Service
Provides authenticated access to Supabase data without exposing tokens
"""
from fastapi import APIRouter, HTTPException, Depends, Cookie, Request
from typing import Optional, List, Dict, Any
import structlog
from supabase import Client

from ..dependencies import get_session_store
from ..services.supabase_session_store_secure import SecureSupabaseSessionStore
from ..services.supabase_auth_proxy import SupabaseAuthProxy
from ..config import settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["data"])

# Initialize auth proxy
auth_proxy = SupabaseAuthProxy()


@router.get("/courses")
async def get_user_courses(
    request: Request,
    gustav_session: Optional[str] = Cookie(None),
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
) -> List[Dict[str, Any]]:
    """Get courses accessible to the authenticated user"""
    if not gustav_session:
        logger.warning("courses_request_no_session")
        raise HTTPException(status_code=401, detail="No session cookie")
    
    try:
        # Validate session
        session_result = await session_store.validate_session(gustav_session)
        if not session_result["is_valid"]:
            logger.warning("courses_request_invalid_session", session_id=gustav_session[:8])
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        user_id = session_result["user_id"]
        
        # Get full session data (includes original access token)
        session_data = await session_store.get_session(gustav_session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Session not found")
        
        logger.info("session_data_retrieved", 
                   user_id=user_id,
                   session_keys=list(session_data.keys()) if session_data else [],
                   has_data_field='data' in session_data if session_data else False,
                   data_type=type(session_data.get('data')) if session_data else None)
        
        # Get authenticated Supabase client
        supabase_client = await auth_proxy.get_authenticated_client(session_data)
        
        # Get user role from session
        user_role = session_result.get("user_role") or session_result.get("role", "student")
        
        # Query courses based on role
        if user_role == "teacher":
            # Teacher: courses where they are creator
            response = supabase_client.table('course')\
                .select('id, name, creator_id')\
                .eq('creator_id', user_id)\
                .execute()
            courses = response.data or []
        else:
            # Student: courses they are assigned to
            response = supabase_client.table('course')\
                .select('id, name, course_student!inner(student_id)')\
                .eq('course_student.student_id', user_id)\
                .execute()
            courses = response.data or []
        
        logger.info("courses_fetched", 
                   user_id=user_id,
                   role=user_role,
                   count=len(courses))
        
        return courses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("courses_fetch_error", 
                    error=str(e),
                    error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Failed to fetch courses")


@router.get("/courses/{course_id}/units")
async def get_course_units(
    course_id: str,
    request: Request,
    gustav_session: Optional[str] = Cookie(None),
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
) -> List[Dict[str, Any]]:
    """Get learning units for a specific course"""
    if not gustav_session:
        logger.warning("units_request_no_session")
        raise HTTPException(status_code=401, detail="No session cookie")
    
    try:
        # Validate session
        session_result = await session_store.validate_session(gustav_session)
        if not session_result["is_valid"]:
            logger.warning("units_request_invalid_session", session_id=gustav_session[:8])
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        user_id = session_result["user_id"]
        
        # Get full session data
        session_data = await session_store.get_session(gustav_session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Session not found")
        
        # Get authenticated Supabase client
        supabase_client = await auth_proxy.get_authenticated_client(session_data)
        
        # Query learning units through the assignment table
        # Note: learning_unit doesn't have course_id directly, it's linked via course_learning_unit_assignment
        response = supabase_client.table('learning_unit')\
            .select('*, course_learning_unit_assignment!inner(course_id)')\
            .eq('course_learning_unit_assignment.course_id', course_id)\
            .order('title')\
            .execute()
        
        logger.info("units_fetched", 
                   user_id=user_id,
                   course_id=course_id,
                   count=len(response.data))
        
        return response.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("units_fetch_error", 
                    error=str(e),
                    course_id=course_id,
                    error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Failed to fetch learning units")


@router.get("/user/progress")
async def get_user_progress(
    request: Request,
    gustav_session: Optional[str] = Cookie(None),
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
) -> Dict[str, Any]:
    """Get learning progress for the authenticated user"""
    if not gustav_session:
        logger.warning("progress_request_no_session")
        raise HTTPException(status_code=401, detail="No session cookie")
    
    try:
        # Validate session
        session_result = await session_store.validate_session(gustav_session)
        if not session_result["is_valid"]:
            logger.warning("progress_request_invalid_session", session_id=gustav_session[:8])
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        user_id = session_result["user_id"]
        
        # Get full session data
        session_data = await session_store.get_session(gustav_session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Session not found")
        
        # Get authenticated Supabase client
        supabase_client = await auth_proxy.get_authenticated_client(session_data)
        
        # Query user progress
        response = supabase_client.table('user_progress')\
            .select('*, learning_units(title, course_id)')\
            .eq('user_id', user_id)\
            .execute()
        
        # Transform data for easier consumption
        progress_by_unit = {
            item['learning_unit_id']: {
                'completed': item['completed'],
                'last_accessed': item['last_accessed'],
                'progress_percentage': item.get('progress_percentage', 0)
            }
            for item in response.data
        }
        
        logger.info("progress_fetched", 
                   user_id=user_id,
                   units_count=len(progress_by_unit))
        
        return {
            "user_id": user_id,
            "progress": progress_by_unit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("progress_fetch_error", 
                    error=str(e),
                    error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Failed to fetch user progress")


@router.get("/user/profile")
async def get_user_profile(
    request: Request,
    gustav_session: Optional[str] = Cookie(None),
    session_store: SecureSupabaseSessionStore = Depends(get_session_store)
) -> Dict[str, Any]:
    """Get user profile data"""
    if not gustav_session:
        logger.warning("profile_request_no_session")
        raise HTTPException(status_code=401, detail="No session cookie")
    
    try:
        # Validate session
        session_result = await session_store.validate_session(gustav_session)
        if not session_result["is_valid"]:
            logger.warning("profile_request_invalid_session", session_id=gustav_session[:8])
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        user_id = session_result["user_id"]
        email = session_result.get("user_email") or session_result.get("email")
        role = session_result.get("user_role") or session_result.get("role")
        
        # Get full session data  
        session_data = await session_store.get_session(gustav_session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Session not found")
        
        # Get authenticated Supabase client
        supabase_client = await auth_proxy.get_authenticated_client(session_data)
        
        # Query user profile
        response = supabase_client.table('profiles')\
            .select('*')\
            .eq('id', user_id)\
            .single()\
            .execute()
        
        profile_data = response.data
        
        # Merge with session data
        profile = {
            "id": user_id,
            "email": email,
            "role": role,
            "full_name": profile_data.get("full_name"),
            "avatar_url": profile_data.get("avatar_url"),
            "created_at": profile_data.get("created_at"),
            "updated_at": profile_data.get("updated_at")
        }
        
        logger.info("profile_fetched", user_id=user_id)
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("profile_fetch_error", 
                    error=str(e),
                    error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")