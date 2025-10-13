#!/usr/bin/env python3
"""
Test Script für die HttpOnly Cookie Auth Integration
Testet die nahtlose Integration in die Streamlit App
"""

import os
import sys
import requests
import time
from pathlib import Path

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(message: str, level: str = "INFO"):
    """Colored logging."""
    color = {"INFO": BLUE, "SUCCESS": GREEN, "ERROR": RED, "WARNING": YELLOW}.get(level, RESET)
    print(f"{color}[{level}] {message}{RESET}")


def test_auth_service():
    """Test if auth service is running."""
    # Try different URLs depending on environment
    urls_to_try = [
        "http://auth:8000/health",  # Docker network
        "http://localhost:8000/health",  # Host network
    ]
    
    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log(f"Auth Service is healthy at {url}", "SUCCESS")
                return True
            else:
                log(f"Auth Service unhealthy at {url}: {response.status_code}", "WARNING")
        except Exception as e:
            log(f"Auth Service not reachable at {url}: {type(e).__name__}", "WARNING")
    
    log("Auth Service not reachable on any URL", "ERROR")
    return False


def test_streamlit_running():
    """Test if Streamlit app is running."""
    try:
        response = requests.get("http://localhost:8501", timeout=5, allow_redirects=False)
        if response.status_code in [200, 302]:
            log("Streamlit app is running", "SUCCESS")
            return True
        else:
            log(f"Streamlit app not responding: {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"Streamlit app not reachable: {e}", "ERROR")
        return False


def test_legacy_auth_fallback():
    """Test if legacy auth still works when auth service is down."""
    log("Testing legacy auth fallback...", "INFO")
    
    # Set environment to force legacy mode
    os.environ["AUTH_MODE"] = "legacy"
    
    try:
        # Import after setting env var
        sys.path.insert(0, "/home/felix/gustav/app")
        from utils.auth_integration import AuthIntegration
        
        mode = AuthIntegration.detect_auth_mode()
        if mode == "legacy":
            log("Legacy auth mode detected correctly", "SUCCESS")
            return True
        else:
            log(f"Wrong auth mode detected: {mode}", "ERROR")
            return False
    except Exception as e:
        log(f"Error testing legacy fallback: {e}", "ERROR")
        return False
    finally:
        # Reset environment
        if "AUTH_MODE" in os.environ:
            del os.environ["AUTH_MODE"]


def test_httponly_detection():
    """Test HttpOnly cookie auth detection."""
    log("Testing HttpOnly cookie auth detection...", "INFO")
    
    # Set environment to force httponly mode
    os.environ["AUTH_MODE"] = "httponly"
    
    try:
        # Import after setting env var
        sys.path.insert(0, "/home/felix/gustav/app")
        from utils.auth_integration import AuthIntegration
        
        mode = AuthIntegration.detect_auth_mode()
        if mode == "httponly":
            log("HttpOnly auth mode detected correctly", "SUCCESS")
            return True
        else:
            log(f"Wrong auth mode detected: {mode}", "ERROR")
            return False
    except Exception as e:
        log(f"Error testing httponly detection: {e}", "ERROR")
        return False
    finally:
        # Reset environment
        if "AUTH_MODE" in os.environ:
            del os.environ["AUTH_MODE"]


def test_docker_services():
    """Test if Docker services are configured correctly."""
    log("Checking Docker services...", "INFO")
    
    # When running inside container, we can't easily check docker compose
    # Instead check if we can resolve service names
    try:
        import socket
        
        services_to_check = [
            ("auth", 8000),
            ("ollama", 11434),
            ("nginx", 80),
        ]
        
        resolved = 0
        for service, port in services_to_check:
            try:
                socket.gethostbyname(service)
                log(f"Service '{service}' is resolvable", "SUCCESS")
                resolved += 1
            except socket.gaierror:
                log(f"Service '{service}' not found in Docker network", "WARNING")
        
        if resolved > 0:
            log(f"Docker networking is working ({resolved} services found)", "SUCCESS")
            return True
        else:
            log("No Docker services found", "ERROR")
            return False
            
    except Exception as e:
        log(f"Error checking Docker services: {e}", "WARNING")
        return False


def test_imports():
    """Test if all necessary imports work."""
    log("Testing imports...", "INFO")
    
    try:
        sys.path.insert(0, "/home/felix/gustav/app")
        
        # Test new imports
        from utils.auth_session import AuthSession
        from utils.auth_integration import AuthIntegration
        log("New auth modules imported successfully", "SUCCESS")
        
        # Test legacy imports still work
        from auth import sign_up, get_user_role
        log("Legacy auth modules still accessible", "SUCCESS")
        
        return True
        
    except ImportError as e:
        log(f"Import error: {e}", "ERROR")
        return False
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        return False


def main():
    """Run all integration tests."""
    print(f"\n{BOLD}=== GUSTAV Auth Integration Test ==={RESET}")
    print(f"Testing HttpOnly Cookie Authentication Integration\n")
    
    tests = [
        ("Import Test", test_imports),
        ("Auth Service Health", test_auth_service),
        ("Streamlit App Running", test_streamlit_running),
        ("Legacy Auth Fallback", test_legacy_auth_fallback),
        ("HttpOnly Auth Detection", test_httponly_detection),
        ("Docker Services", test_docker_services),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{BLUE}Running: {test_name}{RESET}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            log(f"Test crashed: {e}", "ERROR")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{BOLD}=== Test Summary ==={RESET}")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {total - passed}{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}✓ All tests passed! Integration is ready.{RESET}")
    elif passed >= total * 0.7:
        print(f"\n{YELLOW}⚠ Most tests passed. Check warnings above.{RESET}")
    else:
        print(f"\n{RED}✗ Integration has issues. Please check errors.{RESET}")
    
    # Recommendations
    print(f"\n{BOLD}=== Next Steps ==={RESET}")
    if test_auth_service():
        print("1. Test login flow with: python auth_service/test_integration.py")
        print("2. Start Streamlit: cd app && streamlit run main.py")
        print("3. Try logging in with test credentials")
    else:
        print("1. Start auth service: docker compose up auth")
        print("2. Re-run this test")
        print("3. For development: AUTH_MODE=legacy streamlit run app/main.py")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)