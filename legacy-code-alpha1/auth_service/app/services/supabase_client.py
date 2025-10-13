"""
Supabase client for Auth Service
Handles authentication and profile lookups
"""
from supabase import create_client, Client, ClientOptions
from typing import Optional, Dict, Any
import structlog

from app.config import settings

logger = structlog.get_logger()


class SupabaseService:
    """Manages Supabase connections for auth operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        """Get or create Supabase client with anon key"""
        if not self._client:
            options = ClientOptions(
                postgrest_client_timeout=30,
                storage_client_timeout=30
            )
            self._client = create_client(
                settings.SUPABASE_URL, 
                settings.SUPABASE_ANON_KEY,
                options=options
            )
            logger.info("supabase_client_created", type="anon")
        return self._client
    
    @property
    def service_client(self) -> Optional[Client]:
        """Get or create Supabase service client (bypasses RLS)"""
        # Service client is no longer needed with SECURITY DEFINER functions
        # Return None to force usage of anon client with RPC calls
        return None
    
    async def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign up new user with email and password
        
        Args:
            email: User email  
            password: User password
        
        Returns:
            Dict with user, session, and error information
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                logger.info("user_signed_up", 
                           user_id=response.user.id,
                           email=email)
                
                return {
                    "user": response.user,
                    "session": response.session,  # May be None until email confirmed
                    "error": None
                }
            else:
                return {
                    "user": None,
                    "session": None,
                    "error": {"message": "Registration failed"}
                }
                
        except Exception as e:
            logger.error("sign_up_failed", 
                        email=email,
                        error=str(e))
            
            error_msg = str(e)
            
            # Map common errors to user-friendly messages
            if "User already registered" in error_msg:
                error_msg = "Diese E-Mail-Adresse ist bereits registriert"
            elif "rate limit" in error_msg.lower():
                error_msg = "Zu viele Registrierungsversuche. Bitte später erneut versuchen"
            
            return {
                "user": None,
                "session": None,
                "error": {"message": error_msg}
            }
    
    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in user with email and password
        
        Args:
            email: User email
            password: User password
        
        Returns:
            Dict with user, session, and error information
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                logger.info("user_signed_in", 
                           user_id=response.user.id,
                           email=email)
                
                return {
                    "user": response.user,
                    "session": response.session,
                    "error": None
                }
            else:
                return {
                    "user": None,
                    "session": None,
                    "error": {"message": "Invalid credentials"}
                }
                
        except Exception as e:
            logger.error("sign_in_failed", 
                        email=email,
                        error=str(e))
            
            error_msg = str(e)
            if "Invalid login credentials" in error_msg:
                error_msg = "Invalid email or password"
            
            return {
                "user": None,
                "session": None,
                "error": {"message": error_msg}
            }
    
    async def sign_out(self, access_token: str) -> bool:
        """
        Sign out user
        
        Args:
            access_token: User's access token
        
        Returns:
            bool: Success status
        """
        try:
            # Set the session before signing out
            self.client.auth.set_session(access_token, "")
            self.client.auth.sign_out()
            return True
        except Exception as e:
            logger.error("sign_out_failed", error=str(e))
            return False
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: User's refresh token
        
        Returns:
            Dict with new session or error
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            
            if response.session:
                logger.info("token_refreshed", 
                           user_id=response.user.id if response.user else None)
                
                return {
                    "session": response.session,
                    "error": None
                }
            else:
                return {
                    "session": None,
                    "error": {"message": "Token refresh failed"}
                }
                
        except Exception as e:
            logger.error("token_refresh_failed", error=str(e))
            
            return {
                "session": None,
                "error": {"message": str(e)}
            }
    
    async def send_otp_for_password_reset(self, email: str) -> Dict[str, Any]:
        """
        Send OTP code for password reset via email
        
        Args:
            email: User email address
        
        Returns:
            Dict with success status and error information
        """
        try:
            response = self.client.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "should_create_user": False,
                    "data": {"action": "password_reset"}
                }
            })
            
            logger.info("otp_sent_for_password_reset",
                       email_hash=hash(email))
            
            return {
                "success": True,
                "error": None
            }
            
        except Exception as e:
            logger.error("send_otp_failed",
                        email=email,
                        error=str(e))
            
            error_msg = str(e)
            if "rate limit" in error_msg.lower():
                error_msg = "Zu viele Versuche. Bitte warten Sie einige Minuten."
            elif "user not found" in error_msg.lower():
                # Don't reveal if user exists - constant response
                return {
                    "success": True,
                    "error": None
                }
            
            return {
                "success": False,
                "error": {"message": error_msg}
            }
    
    async def verify_otp_and_update_password(self, email: str, otp: str, new_password: str) -> Dict[str, Any]:
        """
        Verify OTP code and update password in one operation
        
        Args:
            email: User email address
            otp: 6-digit OTP code
            new_password: New password to set
        
        Returns:
            Dict with user, session, and error information
        """
        try:
            # Step 1: Verify OTP and get session
            verify_response = self.client.auth.verify_otp({
                "email": email,
                "token": otp,
                "type": "email"
            })
            
            if not verify_response.session:
                logger.error("otp_verification_failed",
                           email_hash=hash(email))
                return {
                    "user": None,
                    "session": None,
                    "error": {"message": "Ungültiger oder abgelaufener Code"}
                }
            
            # Step 2: Update password using the session
            # Set the session first
            self.client.auth.set_session(
                verify_response.session.access_token,
                verify_response.session.refresh_token
            )
            
            # Update the password
            update_response = self.client.auth.update_user({
                "password": new_password
            })
            
            if update_response.user:
                logger.info("password_updated_via_otp",
                           user_id=update_response.user.id,
                           email_hash=hash(email))
                
                return {
                    "user": update_response.user,
                    "session": verify_response.session,
                    "error": None
                }
            else:
                return {
                    "user": None,
                    "session": None,
                    "error": {"message": "Passwort konnte nicht aktualisiert werden"}
                }
                
        except Exception as e:
            logger.error("verify_otp_and_update_password_failed",
                        email_hash=hash(email),
                        error=str(e))
            
            error_msg = str(e)
            if "invalid" in error_msg.lower() or "expired" in error_msg.lower():
                error_msg = "Ungültiger oder abgelaufener Code"
            elif "rate limit" in error_msg.lower():
                error_msg = "Zu viele Versuche. Bitte warten Sie einige Minuten."
            
            return {
                "user": None,
                "session": None,
                "error": {"message": error_msg}
            }
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile including role
        
        Args:
            user_id: User UUID
        
        Returns:
            Profile data or None
        """
        try:
            # Use the SECURITY DEFINER function to bypass RLS
            response = self.client.rpc(
                'get_user_profile_for_auth',
                {'p_user_id': user_id}
            ).execute()
            
            if response.data and len(response.data) > 0:
                # Convert role from enum to string if needed
                profile = response.data[0]
                if profile and 'role' in profile:
                    profile['role'] = str(profile['role'])
                return profile
            
            return None
            
        except Exception as e:
            logger.error("get_profile_failed", 
                        user_id=user_id,
                        error=str(e))
            return None
    
    async def verify_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify access token and get user info
        
        Args:
            access_token: JWT access token
        
        Returns:
            User info or None if invalid
        """
        try:
            # Create a new client with the token
            temp_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_ANON_KEY
            )
            temp_client.auth.set_session(access_token, "")
            
            # Try to get user
            user_response = temp_client.auth.get_user()
            
            if user_response and user_response.user:
                return {
                    "id": user_response.user.id,
                    "email": user_response.user.email,
                    "created_at": user_response.user.created_at
                }
            
            return None
            
        except Exception as e:
            logger.error("token_verification_failed", error=str(e))
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Supabase connectivity"""
        try:
            # Try a simple query
            response = self.client.table('profiles').select('id').limit(1).execute()
            
            return {
                "status": "healthy",
                "healthy": True,
                "url": settings.SUPABASE_URL.split('@')[-1] if '@' in settings.SUPABASE_URL else settings.SUPABASE_URL
            }
            
        except Exception as e:
            return {
                "status": "unhealthy", 
                "healthy": False,
                "error": str(e)
            }


# Singleton instance
supabase_service = SupabaseService()