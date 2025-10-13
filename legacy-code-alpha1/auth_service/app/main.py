"""
FastAPI Auth Service for GUSTAV
Handles HttpOnly cookie-based authentication with Redis session storage
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import os
from datetime import datetime

from app.config import settings
from app.routes import auth, health, session, data_proxy
from app.pages import login, register, forgot_password, reset_password
from app.middleware.security import SecurityHeadersMiddleware
from app.services.secure_session_store import SecureSessionStore
# Import muss erst nach den Services erfolgen, da login.py diese nutzt
from fastapi.staticfiles import StaticFiles

# Initialize secure session store (uses SQL functions, no service key needed!)
session_store = SecureSessionStore()

# Configure structured logging
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("starting_auth_service", 
                version="1.0.0",
                environment=settings.ENVIRONMENT,
                session_storage="supabase_sql_functions",
                security="no_service_key_required")
    
    # Verify Supabase connection
    health = await session_store.health_check()
    if not health.get("healthy"):
        logger.error("supabase_connection_failed", error=health.get("error"))
        raise RuntimeError("Failed to connect to Supabase session storage")
    
    logger.info("supabase_connected", 
                active_sessions=health.get("active_sessions", 0))
    
    # Schedule periodic cleanup of expired sessions
    import asyncio
    
    async def periodic_cleanup():
        while True:
            try:
                await asyncio.sleep(900)  # Every 15 minutes
                deleted = await session_store.cleanup_expired_sessions()
                if deleted > 0:
                    logger.info("periodic_session_cleanup", deleted_count=deleted)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("periodic_cleanup_error", error=str(e))
    
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    logger.info("shutting_down_auth_service")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("auth_service_shutdown_complete")


# Create FastAPI app
app = FastAPI(
    title="GUSTAV Auth Service",
    description="HttpOnly cookie-based authentication service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:8501",
    "http://localhost:8000",
    "http://app:8501",
    f"https://{settings.COOKIE_DOMAIN}",
    f"https://www.{settings.COOKIE_DOMAIN}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# Mount static files
app.mount("/auth/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(login.router, prefix="/auth", tags=["login"])
app.include_router(register.router, prefix="/auth", tags=["register"])
app.include_router(forgot_password.router, prefix="/auth", tags=["password-reset"])
app.include_router(reset_password.router, prefix="/auth", tags=["password-reset"])
app.include_router(session.router, prefix="/auth", tags=["session"])
app.include_router(data_proxy.router, prefix="/auth", tags=["data"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", 
                 path=request.url.path,
                 method=request.method,
                 error=str(exc),
                 exc_type=type(exc).__name__)
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "GUSTAV Auth Service",
        "version": "1.0.0",
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )