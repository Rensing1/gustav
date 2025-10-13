# Copyright (c) 2025 GUSTAV Contributors  
# SPDX-License-Identifier: MIT

"""
Tests for secure session management.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from cryptography.fernet import Fernet
from utils.secure_session import SecureSessionManager, recreate_user_object, recreate_session_object


class TestSecureSessionManager:
    """Tests for SecureSessionManager."""
    
    @pytest.fixture
    def session_manager(self):
        """Create a session manager instance."""
        with patch.dict('os.environ', {'SESSION_ENCRYPTION_KEY': Fernet.generate_key().decode()}):
            return SecureSessionManager()
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user object."""
        user = Mock()
        user.id = "test-user-123"
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock session object."""
        session = Mock()
        session.access_token = "test-access-token"
        session.refresh_token = "test-refresh-token"
        session.expires_at = int(time.time()) + 3600  # 1 hour from now
        return session
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_save_session(self, mock_storage, session_manager, mock_user, mock_session):
        """Test saving session to LocalStorage."""
        # Mock streamlit session state
        with patch('streamlit.session_state', {}):
            result = session_manager.save_session(mock_user, mock_session)
            
            assert result is True
            assert mock_storage.setItem.called
            
            # Verify encrypted data was saved
            call_args = mock_storage.setItem.call_args[0]
            assert call_args[0] == "gustav_secure_session"
            
            # Verify it's encrypted (not readable JSON)
            encrypted_data = call_args[1]
            with pytest.raises(json.JSONDecodeError):
                json.loads(encrypted_data)
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_restore_valid_session(self, mock_storage, session_manager, mock_user, mock_session):
        """Test restoring a valid session from LocalStorage."""
        # Create session data
        session_data = {
            'user_id': mock_user.id,
            'email': mock_user.email,
            'access_token': mock_session.access_token,
            'refresh_token': mock_session.refresh_token,
            'expires_at': mock_session.expires_at,
            'created_at': time.time(),
            'csrf_token': 'test-csrf-token'
        }
        
        # Encrypt the data
        encrypted = session_manager.fernet.encrypt(json.dumps(session_data).encode())
        mock_storage.getItem.return_value = encrypted.decode()
        
        # Restore session
        restored = session_manager.restore_session()
        
        assert restored is not None
        assert restored['user_id'] == mock_user.id
        assert restored['email'] == mock_user.email
        assert restored['access_token'] == mock_session.access_token
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_restore_expired_session(self, mock_storage, session_manager, mock_user, mock_session):
        """Test that expired sessions are not restored."""
        # Create expired session data (20 minutes old)
        session_data = {
            'user_id': mock_user.id,
            'email': mock_user.email,
            'access_token': mock_session.access_token,
            'refresh_token': mock_session.refresh_token,
            'expires_at': mock_session.expires_at,
            'created_at': time.time() - (20 * 60),  # 20 minutes ago
            'csrf_token': 'test-csrf-token'
        }
        
        # Encrypt the data
        encrypted = session_manager.fernet.encrypt(json.dumps(session_data).encode())
        mock_storage.getItem.return_value = encrypted.decode()
        
        # Mock clear_session
        with patch.object(session_manager, 'clear_session') as mock_clear:
            restored = session_manager.restore_session()
            
            assert restored is None
            assert mock_clear.called
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_restore_no_session(self, mock_storage, session_manager):
        """Test restoring when no session exists."""
        mock_storage.getItem.return_value = None
        
        restored = session_manager.restore_session()
        assert restored is None
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_restore_corrupted_session(self, mock_storage, session_manager):
        """Test handling of corrupted session data."""
        # Invalid encrypted data
        mock_storage.getItem.return_value = "invalid-encrypted-data"
        
        restored = session_manager.restore_session()
        assert restored is None
    
    @patch('utils.secure_session.sessionBrowserS')
    @patch('utils.secure_session.get_anon_supabase_client')
    def test_token_refresh(self, mock_client, mock_storage, session_manager, mock_user):
        """Test JWT token refresh."""
        # Create session with expired JWT
        expired_time = int(time.time()) - 100  # Expired
        session_data = {
            'user_id': mock_user.id,
            'email': mock_user.email,
            'access_token': 'old-token',
            'refresh_token': 'refresh-token',
            'expires_at': expired_time,
            'created_at': time.time(),
            'csrf_token': 'test-csrf-token'
        }
        
        # Mock successful refresh
        new_session = Mock()
        new_session.access_token = 'new-access-token'
        new_session.refresh_token = 'new-refresh-token'
        new_session.expires_at = int(time.time()) + 3600
        
        refresh_response = Mock()
        refresh_response.session = new_session
        
        mock_client.return_value.auth.refresh_session.return_value = refresh_response
        
        # Encrypt the data
        encrypted = session_manager.fernet.encrypt(json.dumps(session_data).encode())
        mock_storage.getItem.return_value = encrypted.decode()
        
        # Restore session (should trigger refresh)
        restored = session_manager.restore_session()
        
        assert restored is not None
        assert restored['access_token'] == 'new-access-token'
        assert restored['expires_at'] > expired_time
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_clear_session(self, mock_storage, session_manager):
        """Test clearing session."""
        with patch('streamlit.session_state', {'csrf_token': 'test'}):
            session_manager.clear_session()
            
            assert mock_storage.deleteItem.called
            assert mock_storage.deleteItem.call_args[0][0] == "gustav_secure_session"
    
    @patch('utils.secure_session.sessionBrowserS')
    def test_update_session_timeout(self, mock_storage, session_manager, mock_user, mock_session):
        """Test updating session timeout on activity."""
        # Create session data
        old_time = time.time() - 300  # 5 minutes ago
        session_data = {
            'user_id': mock_user.id,
            'email': mock_user.email,
            'access_token': mock_session.access_token,
            'refresh_token': mock_session.refresh_token,
            'expires_at': mock_session.expires_at,
            'created_at': old_time,
            'csrf_token': 'test-csrf-token'
        }
        
        # Encrypt the data
        encrypted = session_manager.fernet.encrypt(json.dumps(session_data).encode())
        mock_storage.getItem.return_value = encrypted.decode()
        
        # Update timeout
        session_manager.update_session_timeout()
        
        # Verify new data was saved
        assert mock_storage.setItem.called
        
        # Decrypt and check the updated time
        new_encrypted = mock_storage.setItem.call_args[0][1]
        decrypted = session_manager.fernet.decrypt(new_encrypted.encode())
        new_data = json.loads(decrypted.decode())
        
        assert new_data['created_at'] > old_time


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_recreate_user_object(self):
        """Test recreating user object from session data."""
        session_data = {
            'user_id': 'test-123',
            'email': 'test@example.com'
        }
        
        user = recreate_user_object(session_data)
        
        assert user.id == 'test-123'
        assert user.email == 'test@example.com'
    
    def test_recreate_session_object(self):
        """Test recreating session object from session data."""
        session_data = {
            'access_token': 'test-access',
            'refresh_token': 'test-refresh',
            'expires_at': 1234567890
        }
        
        session = recreate_session_object(session_data)
        
        assert session.access_token == 'test-access'
        assert session.refresh_token == 'test-refresh'
        assert session.expires_at == 1234567890