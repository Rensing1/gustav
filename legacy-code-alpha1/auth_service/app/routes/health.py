"""
Health check endpoints for monitoring
"""
from fastapi import APIRouter, Response
from datetime import datetime, timezone
import structlog

from app.models.auth import HealthResponse
from app.services.secure_session_store import SecureSessionStore

# Create session store instance
session_store = SecureSessionStore()
from app.services.supabase_client import supabase_service

router = APIRouter(tags=["health"])
logger = structlog.get_logger()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for monitoring
    Returns service status and dependencies
    """
    # Check Session Storage
    session_health = await session_store.health_check()
    
    # Check Supabase
    supabase_health = await supabase_service.health_check()
    
    # Overall health
    all_healthy = session_health.get("healthy", False) and supabase_health.get("healthy", False)
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={
            "session_storage": session_health,
            "supabase": supabase_health
        }
    )


@router.get("/health/ready")
async def readiness_check(response: Response):
    """
    Readiness probe for Kubernetes/Docker
    Returns 200 if service is ready to accept requests
    """
    # Check if critical services are available
    session_health = await session_store.health_check()
    supabase_health = await supabase_service.health_check()
    
    if not session_health.get("healthy", False):
        response.status_code = 503
        return {"status": "not_ready", "reason": "Session storage unavailable"}
    
    if not supabase_health.get("healthy", False):
        response.status_code = 503
        return {"status": "not_ready", "reason": "Supabase unavailable"}
    
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe for Kubernetes/Docker
    Returns 200 if service is alive (even if dependencies are down)
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}