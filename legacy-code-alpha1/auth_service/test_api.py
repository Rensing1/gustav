#!/usr/bin/env python3
"""
Simple API tests for the auth service
Can be run against the live service in Docker
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"  # When running outside Docker
# BASE_URL = "http://auth:8000"     # When running inside Docker


def test_health_check():
    """Test the health endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data
    assert "services" in data
    print(f"✓ Health check passed: {data['status']}")
    return data


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    print("\nTesting login with invalid credentials...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    print("✓ Invalid login correctly rejected")


def test_session_info_without_cookie():
    """Test accessing session info without cookie"""
    print("\nTesting session info without auth...")
    response = requests.get(f"{BASE_URL}/auth/session/info")
    assert response.status_code == 401
    print("✓ Unauthorized access correctly blocked")


def test_verify_endpoint_without_cookie():
    """Test nginx verify endpoint without cookie"""
    print("\nTesting verify endpoint without auth...")
    response = requests.get(f"{BASE_URL}/auth/verify")
    assert response.status_code == 401
    print("✓ Verify endpoint correctly requires auth")


def run_all_tests():
    """Run all tests"""
    print("="*50)
    print(f"Running Auth Service API Tests")
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*50)
    
    try:
        # Basic connectivity
        health_data = test_health_check()
        
        # Auth tests
        test_login_invalid_credentials()
        test_session_info_without_cookie()
        test_verify_endpoint_without_cookie()
        
        print("\n" + "="*50)
        print("✅ All tests passed!")
        print("="*50)
        
        # Print service details
        print("\nService Status:")
        print(json.dumps(health_data, indent=2))
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Could not connect to {BASE_URL}")
        print("Make sure the auth service is running:")
        print("  docker compose up auth")
        exit(1)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    run_all_tests()