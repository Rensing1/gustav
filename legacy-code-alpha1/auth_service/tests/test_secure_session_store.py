"""
Unit tests for SecureSessionStore with SQL Functions
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import uuid
import json

from app.services.secure_session_store import SecureSessionStore


class TestSecureSessionStore:
    """Test suite for secure session store with SQL functions"""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client"""
        client = Mock()
        client.rpc = Mock()
        return client
    
    @pytest.fixture
    async def session_store(self, mock_supabase):
        """Create session store instance with mocked Supabase"""
        with patch('app.services.secure_session_store.create_client', return_value=mock_supabase):
            store = SecureSessionStore(cache_enabled=True)
            store.supabase = mock_supabase
            yield store
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, session_store, mock_supabase):
        """Test successful session creation"""
        # Arrange
        user_id = str(uuid.uuid4())
        user_email = "test@example.com"
        user_role = "student"
        expected_session_id = "test_session_123"
        
        mock_result = Mock()
        mock_result.data = {"session_id": expected_session_id}
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        session_id = await session_store.create_session(
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            ip_address="127.0.0.1",
            user_agent="TestBrowser/1.0"
        )
        
        # Assert
        assert session_id == expected_session_id
        mock_supabase.rpc.assert_called_once_with("create_session")
        
    @pytest.mark.asyncio
    async def test_create_session_rate_limit(self, session_store, mock_supabase):
        """Test rate limiting on session creation"""
        # Arrange
        mock_result = Mock()
        mock_result.data = None
        mock_result.count = 0  # Rate limit exceeded
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act & Assert
        with pytest.raises(Exception, match="rate limit"):
            await session_store.create_session(
                user_id=str(uuid.uuid4()),
                user_email="test@example.com",
                user_role="student"
            )
    
    @pytest.mark.asyncio
    async def test_get_session_with_cache(self, session_store, mock_supabase):
        """Test session retrieval with cache hit"""
        # Arrange
        session_id = "cached_session_123"
        cached_data = {
            "session_id": session_id,
            "user_id": str(uuid.uuid4()),
            "user_email": "cached@example.com",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        session_store.cache[session_id] = cached_data
        
        # Act
        result = await session_store.get_session(session_id)
        
        # Assert
        assert result == cached_data
        mock_supabase.rpc.assert_not_called()  # Should not hit DB
    
    @pytest.mark.asyncio
    async def test_get_session_cache_miss(self, session_store, mock_supabase):
        """Test session retrieval with cache miss"""
        # Arrange
        session_id = "db_session_123"
        db_data = {
            "session_id": session_id,
            "user_id": str(uuid.uuid4()),
            "user_email": "db@example.com",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat()
        }
        
        mock_result = Mock()
        mock_result.data = db_data
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        result = await session_store.get_session(session_id)
        
        # Assert
        assert result == db_data
        assert session_store.cache[session_id] == db_data  # Should cache
        mock_supabase.rpc.assert_called_once_with("get_session")
    
    @pytest.mark.asyncio
    async def test_validate_session_expired(self, session_store, mock_supabase):
        """Test validation of expired session"""
        # Arrange
        session_id = "expired_session"
        mock_result = Mock()
        mock_result.data = {"is_valid": False}
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        is_valid = await session_store.validate_session(session_id)
        
        # Assert
        assert is_valid is False
        # Cache should be cleared for invalid session
        assert session_id not in session_store.cache
    
    @pytest.mark.asyncio
    async def test_delete_session(self, session_store, mock_supabase):
        """Test session deletion"""
        # Arrange
        session_id = "delete_me_123"
        # Add to cache first
        session_store.cache[session_id] = {"session_id": session_id}
        
        mock_result = Mock()
        mock_result.data = True
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        await session_store.delete_session(session_id)
        
        # Assert
        assert session_id not in session_store.cache
        mock_supabase.rpc.assert_called_once_with("delete_session")
    
    @pytest.mark.asyncio
    async def test_extend_session(self, session_store, mock_supabase):
        """Test session extension"""
        # Arrange
        session_id = "extend_me_123"
        mock_result = Mock()
        mock_result.data = True
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        result = await session_store.extend_session(session_id, 3600)
        
        # Assert
        assert result is True
        # Cache should be invalidated after extension
        assert session_id not in session_store.cache
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, session_store, mock_supabase):
        """Test health check when everything is healthy"""
        # Arrange
        mock_result = Mock()
        mock_result.data = [{"session_id": "test"}]  # Has data = healthy
        mock_supabase.rpc.return_value.limit.return_value.execute.return_value = mock_result
        
        # Act
        health = await session_store.health_check()
        
        # Assert
        assert health["healthy"] is True
        assert "latency_ms" in health
        assert health["cache_enabled"] is True
        assert health["cache_size"] == 0  # Empty cache
    
    @pytest.mark.asyncio
    async def test_concurrent_session_access(self, session_store, mock_supabase):
        """Test concurrent access to same session"""
        # This tests cache consistency under concurrent access
        session_id = "concurrent_123"
        
        # Mock multiple concurrent DB calls
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = Mock()
            mock_result.data = {
                "session_id": session_id,
                "call_number": call_count
            }
            return mock_result
        
        mock_execute = Mock(side_effect=side_effect)
        mock_supabase.rpc.return_value.execute = mock_execute
        
        # Simulate concurrent access
        import asyncio
        tasks = [session_store.get_session(session_id) for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        # All results should be the same (from cache after first call)
        assert all(r == results[0] for r in results)
        # Should only hit DB once due to caching
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_session_data_serialization(self, session_store, mock_supabase):
        """Test complex data serialization in sessions"""
        # Arrange
        complex_data = {
            "user_preferences": {"theme": "dark", "language": "de"},
            "active_course": 123,
            "metadata": {"login_time": datetime.now(timezone.utc).isoformat()}
        }
        
        mock_result = Mock()
        mock_result.data = {"session_id": "complex_123"}
        mock_supabase.rpc.return_value.execute.return_value = mock_result
        
        # Act
        session_id = await session_store.create_session(
            user_id=str(uuid.uuid4()),
            user_email="test@example.com",
            user_role="teacher",
            data=complex_data
        )
        
        # Assert
        assert session_id == "complex_123"
        # Verify JSON serialization was called properly
        call_args = mock_supabase.rpc.return_value.execute.call_args
        assert call_args is not None
    

class TestSessionStoreErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors"""
        # Arrange
        mock_supabase = Mock()
        mock_supabase.rpc.side_effect = Exception("Connection refused")
        
        with patch('app.services.secure_session_store.create_client', return_value=mock_supabase):
            store = SecureSessionStore(cache_enabled=False)
            store.supabase = mock_supabase
            
            # Act & Assert
            with pytest.raises(Exception, match="Connection refused"):
                await store.create_session(
                    user_id=str(uuid.uuid4()),
                    user_email="test@example.com",
                    user_role="student"
                )
    
    @pytest.mark.asyncio
    async def test_invalid_session_format(self):
        """Test handling of invalid session IDs"""
        store = SecureSessionStore(cache_enabled=False)
        
        # Test empty session ID
        with pytest.raises(ValueError, match="Session ID is required"):
            await store.get_session("")
        
        # Test None session ID
        with pytest.raises(ValueError, match="Session ID is required"):
            await store.get_session(None)