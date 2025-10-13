"""
Configuration for FastAPI Auth Service
Compatible with existing GUSTAV architecture
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Auth Service Settings with validation"""
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # Supabase Configuration (reuse from main app)
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    # SUPABASE_SERVICE_KEY: str  # DEPRECATED: No longer needed with SQL functions!
    
    # Redis Configuration (REMOVED - no longer needed)
    # Sessions are now stored in Supabase using SQL functions
    
    # JWT & Security
    SUPABASE_JWT_SECRET: str  # Required for JWT signing
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 90  # Match existing 90-minute sessions
    
    # Cookie Configuration
    COOKIE_DOMAIN: str = "localhost"
    COOKIE_SECURE: bool = False  # Set True in production
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_NAME: str = "gustav_session"
    SESSION_TIMEOUT_MINUTES: int = 90  # Match JWT expiration
    
    # Auth Service Configuration
    AUTH_SERVICE_HOST: str = "0.0.0.0"
    AUTH_SERVICE_PORT: int = 8000
    AUTH_SERVICE_URL: str = "http://auth:8000"
    
    # Site URLs
    SITE_URL: str = "http://localhost:8000"  # Will be overridden in production
    APP_URL: str = "/"  # Main app URL for redirects
    
    # CORS Origins (aligned with main app)
    CORS_ORIGINS: list = [
        "http://localhost:8501",
        "http://localhost:8000",
        "http://app:8501",
        "http://streamlit:8501"
    ]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 5
    RATE_LIMIT_PER_HOUR: int = 60
    
    # Monitoring
    LOG_LEVEL: str = "INFO"
    ENABLE_METRICS: bool = True
    
    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_session_storage_info(self) -> str:
        """Get session storage information"""
        return "Supabase SQL Functions with SECURITY DEFINER"
    
    
    def get_cookie_settings(self) -> dict:
        """Get cookie configuration dict"""
        return {
            "key": self.COOKIE_NAME,
            "max_age": self.SESSION_TIMEOUT_MINUTES * 60,
            "httponly": self.COOKIE_HTTPONLY,
            "secure": self.COOKIE_SECURE,
            "samesite": self.COOKIE_SAMESITE,
            "domain": None if self.ENVIRONMENT == "development" else self.COOKIE_DOMAIN,
            "path": "/"  # Explicitly set path to root for consistency
        }
    
    def update_cors_origins(self):
        """Update CORS origins based on environment"""
        if self.ENVIRONMENT == "production" and self.COOKIE_DOMAIN != "localhost":
            self.CORS_ORIGINS.extend([
                f"https://{self.COOKIE_DOMAIN}",
                f"https://www.{self.COOKIE_DOMAIN}",
                f"https://app.{self.COOKIE_DOMAIN}",
            ])


# Create settings instance
settings = Settings()

# Update CORS origins based on environment
settings.update_cors_origins()

# Validate critical settings
def validate_settings():
    """Validate that all required settings are configured"""
    required = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET"]
    missing = []
    
    for key in required:
        if not getattr(settings, key, None):
            missing.append(key)
    
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    # Validate environment-specific settings
    if settings.ENVIRONMENT == "production":
        if settings.COOKIE_DOMAIN == "localhost":
            print("WARNING: COOKIE_DOMAIN is 'localhost' in production mode")
            # Don't fail for now, just warn
        if not settings.COOKIE_SECURE:
            print("WARNING: COOKIE_SECURE should be True for production")


# Run validation on import
try:
    validate_settings()
    print(f"Auth Service Configuration loaded successfully")
    print(f"  Environment: {settings.ENVIRONMENT}")
    print(f"  Supabase URL: {settings.SUPABASE_URL}")
    print(f"  Session Storage: Supabase SQL Functions (no service key needed!)")
    print(f"  Cookie Domain: {settings.COOKIE_DOMAIN}")
except Exception as e:
    print(f"FATAL: Configuration validation failed: {e}")
    raise