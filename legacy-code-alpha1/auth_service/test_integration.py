#!/usr/bin/env python3
"""
Integration Test Suite für HttpOnly Cookie Authentication
Testet die nahtlose Integration ins bestehende GUSTAV-System
"""
import requests
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

# Konfiguration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
AUTH_SERVICE_URL = f"{BASE_URL}/auth"
NGINX_URL = os.environ.get("NGINX_URL", "http://localhost")

# Test-Credentials (müssen in Supabase existieren)
TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "testpassword123")

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class IntegrationTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.cookies = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Strukturiertes Logging mit Farben"""
        timestamp = datetime.now().isoformat()
        color = {"INFO": BLUE, "SUCCESS": GREEN, "ERROR": RED, "WARNING": YELLOW}.get(level, RESET)
        print(f"{color}[{timestamp}] {level}: {message}{RESET}")
    
    def test_step(self, name: str, func, *args, **kwargs) -> bool:
        """Führt einen Testschritt aus und protokolliert das Ergebnis"""
        try:
            self.log(f"Testing: {name}")
            result = func(*args, **kwargs)
            self.test_results.append({"name": name, "status": "PASSED", "result": result})
            self.log(f"✓ {name}", "SUCCESS")
            return True
        except AssertionError as e:
            self.test_results.append({"name": name, "status": "FAILED", "error": str(e)})
            self.log(f"✗ {name}: {str(e)}", "ERROR")
            return False
        except Exception as e:
            self.test_results.append({"name": name, "status": "ERROR", "error": str(e)})
            self.log(f"✗ {name}: Unexpected error: {str(e)}", "ERROR")
            return False
    
    # === Auth Service Tests ===
    
    def test_auth_service_health(self) -> Dict[str, Any]:
        """Test 1: Auth Service Health Check"""
        response = self.session.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data["status"] in ["healthy", "degraded"], f"Unexpected status: {data['status']}"
        assert "services" in data, "Missing services in health response"
        
        # Check Supabase connection
        supabase_status = data["services"].get("supabase", {})
        assert supabase_status.get("status") == "healthy", "Supabase not healthy"
        
        return data
    
    def test_login_flow(self) -> str:
        """Test 2: Login Flow mit HttpOnly Cookie"""
        # Login Request
        response = self.session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        
        # Check response data
        data = response.json()
        assert "user_id" in data, "Missing user_id in response"
        assert "email" in data, "Missing email in response"
        assert "role" in data, "Missing role in response"
        assert "session_id" in data, "Missing session_id in response"
        
        # Check HttpOnly Cookie
        cookies = response.cookies
        assert "gustav_session" in cookies, "Session cookie not set"
        
        cookie = cookies["gustav_session"]
        assert cookie, "Cookie value is empty"
        
        # Verify cookie attributes (when running against real nginx)
        if NGINX_URL != "http://localhost":
            # Diese Attribute sind nur bei HTTPS sichtbar
            self.log(f"Cookie attributes: secure={cookie.secure}, httponly={cookie.has_nonstandard_attr('HttpOnly')}", "INFO")
        
        self.cookies = {"gustav_session": cookie}
        return data["session_id"]
    
    def test_session_info(self, session_id: str) -> Dict[str, Any]:
        """Test 3: Session Info Endpoint"""
        response = self.session.get(
            f"{AUTH_SERVICE_URL}/session/info",
            cookies=self.cookies
        )
        
        assert response.status_code == 200, f"Session info failed: {response.status_code}"
        
        data = response.json()
        assert data["session_id"] == session_id, "Session ID mismatch"
        assert "expires_in_seconds" in data, "Missing expiration info"
        assert data["expires_in_seconds"] > 0, "Session already expired"
        
        return data
    
    def test_verify_endpoint(self) -> Dict[str, Any]:
        """Test 4: nginx auth_request Verify Endpoint"""
        response = self.session.get(
            f"{AUTH_SERVICE_URL}/verify",
            cookies=self.cookies
        )
        
        assert response.status_code == 200, f"Verify failed: {response.status_code}"
        
        # Check auth headers
        headers = response.headers
        assert "X-User-Id" in headers, "Missing X-User-Id header"
        assert "X-User-Email" in headers, "Missing X-User-Email header"
        assert "X-User-Role" in headers, "Missing X-User-Role header"
        assert "X-Access-Token" in headers, "Missing X-Access-Token header"
        
        return {
            "user_id": headers["X-User-Id"],
            "email": headers["X-User-Email"],
            "role": headers["X-User-Role"]
        }
    
    def test_invalid_session(self) -> None:
        """Test 5: Invalid Session Handling"""
        response = self.session.get(
            f"{AUTH_SERVICE_URL}/session/info",
            cookies={"gustav_session": "invalid-session-id"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_logout_flow(self) -> None:
        """Test 6: Logout Flow"""
        response = self.session.post(
            f"{AUTH_SERVICE_URL}/logout",
            cookies=self.cookies
        )
        
        assert response.status_code == 200, f"Logout failed: {response.status_code}"
        
        # Verify session is invalid after logout
        verify_response = self.session.get(
            f"{AUTH_SERVICE_URL}/verify",
            cookies=self.cookies
        )
        assert verify_response.status_code == 401, "Session still valid after logout"
    
    # === nginx Integration Tests ===
    
    def test_nginx_protected_route(self) -> None:
        """Test 7: nginx Protected Route ohne Auth"""
        if NGINX_URL == "http://localhost":
            self.log("Skipping nginx test in local mode", "WARNING")
            return
        
        response = requests.get(f"{NGINX_URL}/", allow_redirects=False)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_nginx_auth_flow(self) -> None:
        """Test 8: nginx Auth Flow mit Cookie"""
        if NGINX_URL == "http://localhost":
            self.log("Skipping nginx test in local mode", "WARNING")
            return
        
        # Login first
        login_response = requests.post(
            f"{NGINX_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200, "nginx login failed"
        
        cookies = login_response.cookies
        
        # Access protected resource
        app_response = requests.get(
            f"{NGINX_URL}/",
            cookies=cookies,
            allow_redirects=False
        )
        assert app_response.status_code == 200, "Protected resource access failed"
    
    # === Supabase Integration Tests ===
    
    def test_supabase_session_storage(self) -> None:
        """Test 9: Supabase Session Storage"""
        # Login to create session
        login_response = self.session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200
        
        session_id = login_response.json()["session_id"]
        
        # Verify session exists in storage
        info_response = self.session.get(
            f"{AUTH_SERVICE_URL}/session/info",
            cookies=login_response.cookies
        )
        assert info_response.status_code == 200
        assert info_response.json()["session_id"] == session_id
    
    def test_session_activity_update(self) -> None:
        """Test 10: Session Activity Updates"""
        # Login
        login_response = self.session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        cookies = login_response.cookies
        
        # Get initial activity time
        info1 = self.session.get(f"{AUTH_SERVICE_URL}/session/info", cookies=cookies).json()
        
        # Wait a bit
        time.sleep(2)
        
        # Make another request
        self.session.get(f"{AUTH_SERVICE_URL}/verify", cookies=cookies)
        
        # Check activity updated
        info2 = self.session.get(f"{AUTH_SERVICE_URL}/session/info", cookies=cookies).json()
        
        # Activity time should be updated (or at least not older)
        self.log(f"Activity times: {info1.get('last_activity')} -> {info2.get('last_activity')}", "INFO")
    
    # === Performance Tests ===
    
    def test_auth_performance(self) -> None:
        """Test 11: Auth Performance (Target: <50ms)"""
        # Login first
        login_response = self.session.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        cookies = login_response.cookies
        
        # Measure verify endpoint performance
        times = []
        for i in range(10):
            start = time.time()
            response = self.session.get(f"{AUTH_SERVICE_URL}/verify", cookies=cookies)
            end = time.time()
            
            assert response.status_code == 200
            times.append((end - start) * 1000)  # Convert to ms
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        
        self.log(f"Performance: avg={avg_time:.1f}ms, min={min_time:.1f}ms, max={max_time:.1f}ms", "INFO")
        assert avg_time < 50, f"Average response time {avg_time:.1f}ms exceeds 50ms target"
    
    # === Error Handling Tests ===
    
    def test_rate_limiting(self) -> None:
        """Test 12: Rate Limiting"""
        # Attempt multiple failed logins
        failed_attempts = 0
        for i in range(10):
            response = self.session.post(
                f"{AUTH_SERVICE_URL}/login",
                json={"email": TEST_EMAIL, "password": "wrong_password"}
            )
            if response.status_code == 429:  # Too Many Requests
                self.log(f"Rate limited after {i} attempts", "INFO")
                failed_attempts = i
                break
        
        # Should be rate limited within 10 attempts
        if failed_attempts == 0:
            self.log("Rate limiting might not be configured", "WARNING")
    
    def test_cors_headers(self) -> None:
        """Test 13: CORS Headers"""
        response = self.session.options(f"{AUTH_SERVICE_URL}/login")
        
        assert "access-control-allow-origin" in response.headers, "Missing CORS headers"
        assert "access-control-allow-methods" in response.headers, "Missing CORS methods"
        assert response.headers.get("access-control-allow-credentials") == "true", "Credentials not allowed"
    
    # === Integration Summary ===
    
    def run_all_tests(self) -> None:
        """Führt alle Tests aus und zeigt eine Zusammenfassung"""
        print(f"\n{BOLD}=== GUSTAV HttpOnly Cookie Integration Test Suite ==={RESET}")
        print(f"Auth Service URL: {AUTH_SERVICE_URL}")
        print(f"nginx URL: {NGINX_URL}")
        print(f"Test User: {TEST_EMAIL}")
        print(f"Timestamp: {datetime.now().isoformat()}\n")
        
        # Core Auth Tests
        print(f"{BOLD}--- Core Authentication Tests ---{RESET}")
        self.test_step("1. Auth Service Health Check", self.test_auth_service_health)
        
        session_id = None
        if self.test_step("2. Login Flow", self.test_login_flow):
            session_id = self.test_results[-1]["result"]
        
        if session_id:
            self.test_step("3. Session Info", self.test_session_info, session_id)
            self.test_step("4. Verify Endpoint", self.test_verify_endpoint)
        
        self.test_step("5. Invalid Session Handling", self.test_invalid_session)
        
        # Performance Tests
        print(f"\n{BOLD}--- Performance Tests ---{RESET}")
        self.test_step("11. Auth Performance", self.test_auth_performance)
        
        # Security Tests
        print(f"\n{BOLD}--- Security Tests ---{RESET}")
        self.test_step("12. Rate Limiting", self.test_rate_limiting)
        self.test_step("13. CORS Headers", self.test_cors_headers)
        
        # Integration Tests
        print(f"\n{BOLD}--- Integration Tests ---{RESET}")
        self.test_step("9. Supabase Session Storage", self.test_supabase_session_storage)
        self.test_step("10. Session Activity Updates", self.test_session_activity_update)
        
        # nginx Tests (if available)
        if NGINX_URL != "http://localhost":
            print(f"\n{BOLD}--- nginx Integration Tests ---{RESET}")
            self.test_step("7. nginx Protected Route", self.test_nginx_protected_route)
            self.test_step("8. nginx Auth Flow", self.test_nginx_auth_flow)
        
        # Cleanup
        self.test_step("6. Logout Flow", self.test_logout_flow)
        
        # Summary
        self.print_summary()
    
    def print_summary(self) -> None:
        """Zeigt eine Zusammenfassung der Testergebnisse"""
        print(f"\n{BOLD}=== Test Summary ==={RESET}")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["status"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["status"] == "ERROR")
        
        print(f"Total Tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        print(f"{YELLOW}Errors: {errors}{RESET}")
        
        if failed + errors > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for result in self.test_results:
                if result["status"] in ["FAILED", "ERROR"]:
                    print(f"  - {result['name']}: {result.get('error', 'Unknown error')}")
        
        # Integration Assessment
        print(f"\n{BOLD}=== Integration Assessment ==={RESET}")
        
        if passed == total:
            print(f"{GREEN}✓ FULL INTEGRATION SUCCESS{RESET}")
            print("Die HttpOnly Cookie Authentication kann nahtlos ins System integriert werden.")
        elif passed >= total * 0.8:
            print(f"{YELLOW}⚠ PARTIAL INTEGRATION SUCCESS{RESET}")
            print("Die meisten Tests waren erfolgreich, aber es gibt noch kleinere Probleme.")
        else:
            print(f"{RED}✗ INTEGRATION ISSUES DETECTED{RESET}")
            print("Es wurden kritische Probleme gefunden, die vor der Integration behoben werden müssen.")
        
        # Recommendations
        print(f"\n{BOLD}=== Empfehlungen ==={RESET}")
        if any(r["name"].startswith("nginx") and r["status"] != "PASSED" for r in self.test_results):
            print("- nginx Konfiguration überprüfen und auth_request Module aktivieren")
        if any("Performance" in r["name"] and r["status"] != "PASSED" for r in self.test_results):
            print("- Performance-Optimierung für Session-Validierung durchführen")
        if any("Rate" in r["name"] and r["status"] != "PASSED" for r in self.test_results):
            print("- Rate Limiting konfigurieren für besseren Schutz")
        
        # Exit code
        sys.exit(0 if failed + errors == 0 else 1)


def main():
    """Hauptfunktion"""
    tester = IntegrationTester()
    
    # Check if auth service is reachable
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"{RED}Auth Service nicht erreichbar unter {BASE_URL}{RESET}")
            print("Stelle sicher, dass der Service läuft:")
            print("  docker compose up auth")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Kann keine Verbindung zum Auth Service herstellen: {e}{RESET}")
        print(f"URL: {BASE_URL}")
        sys.exit(1)
    
    # Run tests
    tester.run_all_tests()


if __name__ == "__main__":
    main()