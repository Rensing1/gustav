#!/usr/bin/env python3
"""
Test script for session-based auth integration
"""

import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "mustermann@gymalf.de"
TEST_PASSWORD = "123456"

def test_session_integration():
    """Test the complete session flow"""
    
    print("=== Session-Based Auth Integration Test ===\n")
    
    # Step 1: Login
    print("1. Testing login...")
    login_response = requests.post(
        f"{BASE_URL}/auth/api/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        return False
    
    print("✅ Login successful")
    print(f"   User: {login_response.json().get('email')}")
    print(f"   Role: {login_response.json().get('role')}")
    
    # Extract session cookie
    cookies = login_response.cookies
    session_cookie = cookies.get('gustav_session')
    
    if not session_cookie:
        print("❌ No session cookie received")
        return False
    
    print(f"✅ Session cookie received: {session_cookie[:20]}...")
    
    # Step 2: Test /session/me endpoint
    print("\n2. Testing /session/me endpoint...")
    session_me_response = requests.get(
        f"{BASE_URL}/auth/session/me",
        cookies={'gustav_session': session_cookie}
    )
    
    if session_me_response.status_code != 200:
        print(f"❌ /session/me failed: {session_me_response.status_code}")
        print(f"   Response: {session_me_response.text}")
        return False
    
    session_data = session_me_response.json()
    print("✅ Session data retrieved:")
    print(f"   User ID: {session_data.get('user_id')}")
    print(f"   Email: {session_data.get('email')}")
    print(f"   Role: {session_data.get('role')}")
    print(f"   Expires at: {session_data.get('expires_at')}")
    
    # Step 3: Test /session/validate endpoint
    print("\n3. Testing /session/validate endpoint...")
    validate_response = requests.get(
        f"{BASE_URL}/auth/session/validate",
        cookies={'gustav_session': session_cookie}
    )
    
    if validate_response.status_code != 200:
        print(f"❌ /session/validate failed: {validate_response.status_code}")
        return False
    
    validation = validate_response.json()
    print(f"✅ Session validation: {'Valid' if validation.get('valid') else 'Invalid'}")
    if validation.get('user_id'):
        print(f"   User ID confirmed: {validation.get('user_id')}")
    
    # Step 4: Test invalid session
    print("\n4. Testing invalid session handling...")
    invalid_response = requests.get(
        f"{BASE_URL}/auth/session/me",
        cookies={'gustav_session': 'invalid_session_id'}
    )
    
    if invalid_response.status_code == 401:
        print("✅ Invalid session correctly rejected (401)")
    else:
        print(f"❌ Unexpected status for invalid session: {invalid_response.status_code}")
    
    # Step 5: Test no cookie
    print("\n5. Testing no cookie handling...")
    no_cookie_response = requests.get(f"{BASE_URL}/auth/session/me")
    
    if no_cookie_response.status_code == 401:
        print("✅ No cookie correctly rejected (401)")
    else:
        print(f"❌ Unexpected status for no cookie: {no_cookie_response.status_code}")
    
    # Step 6: Logout
    print("\n6. Testing logout...")
    logout_response = requests.post(
        f"{BASE_URL}/auth/logout",
        cookies={'gustav_session': session_cookie}
    )
    
    if logout_response.status_code == 200:
        print("✅ Logout successful")
    else:
        print(f"❌ Logout failed: {logout_response.status_code}")
    
    # Step 7: Verify session is invalid after logout
    print("\n7. Verifying session is invalid after logout...")
    post_logout_response = requests.get(
        f"{BASE_URL}/auth/session/validate",
        cookies={'gustav_session': session_cookie}
    )
    
    if post_logout_response.status_code == 200:
        validation = post_logout_response.json()
        if not validation.get('valid'):
            print("✅ Session correctly invalidated after logout")
        else:
            print("❌ Session still valid after logout!")
            return False
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    success = test_session_integration()
    sys.exit(0 if success else 1)