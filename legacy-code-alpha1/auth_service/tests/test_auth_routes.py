"""
Test auth routes and endpoints
"""
import pytest
from unittest.mock import Mock, patch
import uuid
from datetime import datetime, timezone
import json


class TestAuthRoutes:
    """Test authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, test_client, mock_supabase_client, auth_headers):
        """Test successful login"""
        # Arrange
        user_id = str(uuid.uuid4())
        mock_auth_response = Mock()
        mock_auth_response.user.id = user_id
        mock_auth_response.user.email = "test@example.com"
        mock_auth_response.session.access_token = "test_access_token"
        mock_auth_response.session.refresh_token = "test_refresh_token"
        mock_auth_response.session.expires_at = 1234567890
        
        mock_supabase_client.auth.sign_in_with_password.return_value = mock_auth_response
        
        # Mock profile query
        mock_profile = Mock()
        mock_profile.data = {"role": "student"}
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_profile
        
        # Mock session creation
        with patch('app.routes.auth.session_store.create_session', return_value="session_123"):
            # Act
            response = test_client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "password123"},
                headers=auth_headers
            )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful"
        assert data["user_id"] == user_id
        assert data["email"] == "test@example.com"
        assert data["role"] == "student"
        
        # Check cookie was set
        assert "gustav_session" in response.cookies
    
    @pytest.mark.asyncio 
    async def test_login_invalid_credentials(self, test_client, mock_supabase_client):
        """Test login with invalid credentials"""
        # Arrange
        mock_supabase_client.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
        
        # Act
        response = test_client.post(
            "/auth/login",
            json={"email": "invalid@example.com", "password": "wrong"}
        )
        
        # Assert
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_logout_success(self, test_client):
        """Test successful logout"""
        # Arrange
        session_id = "test_session_123"
        
        with patch('app.routes.auth.get_current_session', return_value=session_id):
            with patch('app.routes.auth.session_store.delete_session') as mock_delete:
                # Act
                response = test_client.post(
                    "/auth/logout",
                    cookies={"gustav_session": session_id}
                )
                
                # Assert
                assert response.status_code == 200
                assert response.json()["message"] == "Logged out successfully"
                mock_delete.assert_called_once_with(session_id)
                
                # Cookie should be deleted
                assert response.cookies.get("gustav_session") == '""'
    
    @pytest.mark.asyncio
    async def test_session_info_valid(self, test_client):
        """Test getting session info for valid session"""
        # Arrange
        session_data = {
            "session_id": "test_123",
            "user_id": str(uuid.uuid4()),
            "user_email": "test@example.com",
            "user_role": "teacher",
            "expires_at": "2025-01-01T00:00:00Z",
            "created_at": "2024-12-01T00:00:00Z"
        }
        
        with patch('app.routes.auth.get_current_session_data', return_value=session_data):
            # Act
            response = test_client.get(
                "/auth/session/info",
                cookies={"gustav_session": "test_123"}
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == session_data["user_id"]
            assert data["user_email"] == session_data["user_email"]
            assert data["user_role"] == session_data["user_role"]
    
    @pytest.mark.asyncio
    async def test_session_info_invalid(self, test_client):
        """Test session info with invalid session"""
        # Arrange
        with patch('app.routes.auth.get_current_session_data', return_value=None):
            # Act
            response = test_client.get(
                "/auth/session/info",
                cookies={"gustav_session": "invalid_session"}
            )
            
            # Assert
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_verify_endpoint(self, test_client):
        """Test nginx auth_request verify endpoint"""
        # Arrange
        session_data = {
            "user_id": str(uuid.uuid4()),
            "user_email": "verified@example.com",
            "user_role": "admin",
            "access_token": "test_token"
        }
        
        with patch('app.routes.auth.get_current_session_data', return_value=session_data):
            with patch('app.routes.auth.session_store.validate_session', return_value=True):
                # Act
                response = test_client.get(
                    "/auth/verify",
                    cookies={"gustav_session": "valid_session"}
                )
                
                # Assert
                assert response.status_code == 200
                assert response.headers["X-User-Id"] == session_data["user_id"]
                assert response.headers["X-User-Email"] == session_data["user_email"]
                assert response.headers["X-User-Role"] == session_data["user_role"]
                assert response.headers["X-Access-Token"] == session_data["access_token"]
    
    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        """Test health check endpoint"""
        # Arrange
        mock_session_health = {"healthy": True, "latency_ms": 5}
        mock_supabase_health = {"healthy": True, "latency_ms": 10}
        
        with patch('app.routes.health.session_store.health_check', return_value=mock_session_health):
            with patch('app.routes.health.supabase_service.health_check', return_value=mock_supabase_health):
                # Act
                response = test_client.get("/health")
                
                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert "timestamp" in data
                assert data["services"]["session_storage"]["healthy"] is True
                assert data["services"]["supabase"]["healthy"] is True


class TestAuthMiddleware:
    """Test authentication middleware behavior"""
    
    @pytest.mark.asyncio
    async def test_missing_session_cookie(self, test_client):
        """Test request without session cookie"""
        with patch('app.dependencies.get_current_session', side_effect=Exception("No session")):
            response = test_client.get("/auth/session/info")
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_session(self, test_client):
        """Test request with expired session"""
        with patch('app.routes.auth.session_store.validate_session', return_value=False):
            response = test_client.get(
                "/auth/session/info",
                cookies={"gustav_session": "expired_session"}
            )
            assert response.status_code == 401