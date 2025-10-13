"""
Pytest configuration and shared fixtures
"""
import pytest
import os
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test_anon_key"
os.environ["SUPABASE_JWT_SECRET"] = "test_jwt_secret"
os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_DOMAIN"] = "localhost"


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing"""
    client = Mock()
    
    # Mock auth methods
    client.auth.sign_in_with_password = Mock()
    client.auth.sign_out = Mock()
    
    # Mock table operations
    client.table = Mock()
    
    # Mock RPC calls
    client.rpc = Mock()
    
    return client


@pytest.fixture
def test_client(mock_supabase_client):
    """Create FastAPI test client"""
    with patch('app.services.supabase_client.supabase', mock_supabase_client):
        from app.main import app
        client = TestClient(app)
        yield client


@pytest.fixture
def auth_headers():
    """Common auth headers for testing"""
    return {
        "Content-Type": "application/json",
        "X-Forwarded-For": "127.0.0.1",
        "User-Agent": "pytest/test"
    }