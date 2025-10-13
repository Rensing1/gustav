# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta

from auth import request_password_reset, update_password, _is_gymalf_email, _check_password_reset_rate_limit, PASSWORD_RESET_REQUESTS_KEY


class TestPasswordResetValidation:
    """Tests für Email-Validierung und Rate-Limiting."""
    
    def test_is_gymalf_email_valid(self):
        """Test: Gültige @gymalf.de Email."""
        assert _is_gymalf_email("test@gymalf.de") is True
        assert _is_gymalf_email("Test.User@gymalf.de") is True  # Case insensitive
        assert _is_gymalf_email("teacher123@gymalf.de") is True
    
    def test_is_gymalf_email_invalid(self):
        """Test: Ungültige Email-Domains."""
        assert _is_gymalf_email("test@gmail.com") is False
        assert _is_gymalf_email("user@example.com") is False
        assert _is_gymalf_email("@gymalf.de") is False
        assert _is_gymalf_email("test@") is False
        assert _is_gymalf_email("invalid") is False
    
    def test_rate_limit_first_request(self):
        """Test: Erster Request ist immer erlaubt."""
        session_store = {}
        assert _check_password_reset_rate_limit("test@gymalf.de", session_store) is True
    
    def test_rate_limit_within_limit(self):
        """Test: Zweiter Request innerhalb einer Stunde ist erlaubt."""
        email = "test@gymalf.de"
        session_store = {
            PASSWORD_RESET_REQUESTS_KEY: {
                email: [datetime.now() - timedelta(minutes=30)]
            }
        }
        assert _check_password_reset_rate_limit(email, session_store) is True
    
    def test_rate_limit_exceeded(self):
        """Test: Dritter Request wird blockiert."""
        email = "test@gymalf.de"
        now = datetime.now()
        session_store = {
            PASSWORD_RESET_REQUESTS_KEY: {
                email: [now - timedelta(minutes=30), now - timedelta(minutes=15)]
            }
        }
        assert _check_password_reset_rate_limit(email, session_store) is False
    
    def test_rate_limit_cleanup_old_requests(self):
        """Test: Alte Requests (>1h) werden bereinigt."""
        email = "test@gymalf.de"
        now = datetime.now()
        session_store = {
            PASSWORD_RESET_REQUESTS_KEY: {
                email: [
                    now - timedelta(hours=2),  # Alt - sollte entfernt werden
                    now - timedelta(minutes=30)  # Recent - bleibt
                ]
            }
        }
        assert _check_password_reset_rate_limit(email, session_store) is True
        # Check cleanup
        assert len(session_store[PASSWORD_RESET_REQUESTS_KEY][email]) == 1


class TestPasswordResetFunction:
    """Tests für request_password_reset()."""
    
    def test_request_password_reset_success(self):
        """Test: Erfolgreicher Password-Reset-Request."""
        # Mock Supabase client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.error = None
        mock_client.auth.reset_password_email.return_value = mock_response
        
        # Session store
        session_store = {}
        
        result = request_password_reset(
            email="test@gymalf.de",
            auth_client=mock_client,
            session_store=session_store,
            site_url="https://example.com"
        )
        
        assert result["success"] is True
        assert result["error"] is None
        mock_client.auth.reset_password_email.assert_called_once_with(
            email="test@gymalf.de",
            redirect_to="https://example.com?type=recovery"
        )
    
    def test_request_password_reset_invalid_email(self):
        """Test: Ungültige Email wird abgelehnt."""
        mock_client = Mock()
        session_store = {}
        
        result = request_password_reset(
            email="invalid@gmail.com",
            auth_client=mock_client,
            session_store=session_store
        )
        
        assert result["success"] is False
        assert "Nur @gymalf.de Email-Adressen" in result["error"]
    
    def test_request_password_reset_rate_limited(self):
        """Test: Rate-Limit wird durchgesetzt."""
        mock_client = Mock()
        # Session store mit Rate-Limit erreicht
        email = "test@gymalf.de"
        now = datetime.now()
        session_store = {
            PASSWORD_RESET_REQUESTS_KEY: {
                email: [now - timedelta(minutes=30), now - timedelta(minutes=15)]
            }
        }
        
        result = request_password_reset(
            email=email,
            auth_client=mock_client,
            session_store=session_store
        )
        
        assert result["success"] is False
        assert "Zu viele Anfragen" in result["error"]
    
    def test_request_password_reset_supabase_error(self):
        """Test: Supabase-Fehler wird korrekt behandelt."""
        # Mock Supabase error response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.error = Mock()
        mock_response.error.message = "User not found"
        mock_client.auth.reset_password_email.return_value = mock_response
        
        session_store = {}
        
        result = request_password_reset(
            email="test@gymalf.de",
            auth_client=mock_client,
            session_store=session_store
        )
        
        assert result["success"] is False
        assert "User not found" in result["error"]


class TestPasswordUpdate:
    """Tests für update_password()."""
    
    def test_update_password_success(self):
        """Test: Erfolgreiches Passwort-Update."""
        # Mock Supabase client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.error = None
        mock_client.auth.update_user.return_value = mock_response
        
        result = update_password(
            new_password="newpassword123",
            auth_client=mock_client
        )
        
        assert result["success"] is True
        assert result["error"] is None
        mock_client.auth.update_user.assert_called_once_with(
            {"password": "newpassword123"}
        )
    
    def test_update_password_too_short(self):
        """Test: Zu kurzes Passwort wird abgelehnt."""
        mock_client = Mock()
        
        result = update_password(
            new_password="12345",  # Nur 5 Zeichen
            auth_client=mock_client
        )
        
        assert result["success"] is False
        assert "mindestens 6 Zeichen" in result["error"]
    
    def test_update_password_supabase_error(self):
        """Test: Supabase-Fehler beim Update."""
        # Mock Supabase error response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.error = Mock()
        mock_response.error.message = "Session expired"
        mock_client.auth.update_user.return_value = mock_response
        
        result = update_password(
            new_password="newpassword123",
            auth_client=mock_client
        )
        
        assert result["success"] is False
        assert "Session expired" in result["error"]


# Fixture nicht mehr benötigt - wir verwenden lokale Dicts statt Streamlit Session State