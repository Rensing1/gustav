#!/usr/bin/env python3
"""
GUSTAV System Integration Test
Testet die nahtlose Integration der HttpOnly Cookie Authentication
in das bestehende GUSTAV System mit allen Komponenten
"""
import requests
import subprocess
import json
import time
from pathlib import Path
import os
import sys
from typing import Dict, Any, List

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class SystemIntegrationTester:
    def __init__(self):
        self.project_root = Path("/home/felix/gustav")
        self.results = []
        
    def log(self, message: str, level: str = "INFO"):
        """Formatiertes Logging"""
        color = {"INFO": BLUE, "SUCCESS": GREEN, "ERROR": RED, "WARNING": YELLOW}.get(level, RESET)
        print(f"{color}[{level}] {message}{RESET}")
    
    def run_command(self, command: str, cwd: Path = None) -> Dict[str, Any]:
        """Führt einen Shell-Befehl aus und gibt das Ergebnis zurück"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                cwd=cwd or self.project_root,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_docker_services(self) -> bool:
        """Test 1: Docker Services Status"""
        self.log("Checking Docker services status...")
        
        # Check if docker compose is available
        result = self.run_command("docker compose version")
        if not result["success"]:
            self.log("Docker Compose not available", "ERROR")
            return False
        
        # Check service status
        result = self.run_command("docker compose ps --format json")
        if not result["success"]:
            self.log("Could not get service status", "ERROR")
            return False
        
        try:
            services = json.loads(result["stdout"]) if result["stdout"] else []
            if not isinstance(services, list):
                services = [services]
            
            critical_services = ["gustav_app", "gustav_auth", "gustav_nginx"]
            running_services = [s["Name"] for s in services if s.get("State") == "running"]
            
            self.log(f"Running services: {running_services}")
            
            missing_services = [s for s in critical_services if s not in running_services]
            if missing_services:
                self.log(f"Missing critical services: {missing_services}", "WARNING")
                return False
            
            self.log("All critical services are running", "SUCCESS")
            return True
            
        except json.JSONDecodeError:
            self.log("Could not parse service status", "ERROR")
            return False
    
    def test_auth_service_health(self) -> bool:
        """Test 2: Auth Service Health"""
        self.log("Testing Auth Service health...")
        
        try:
            # Test direct health endpoint
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log("Auth Service is healthy", "SUCCESS")
                    return True
                else:
                    self.log(f"Auth Service unhealthy: {data}", "ERROR")
                    return False
            else:
                self.log(f"Auth Service health check failed: {response.status_code}", "ERROR")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log(f"Could not reach Auth Service: {e}", "ERROR")
            return False
    
    def test_streamlit_app_health(self) -> bool:
        """Test 3: Streamlit App Health"""
        self.log("Testing Streamlit App health...")
        
        try:
            # Test if Streamlit responds
            response = requests.get("http://localhost:8501", timeout=10, allow_redirects=False)
            if response.status_code in [200, 302]:  # 302 might be a redirect to login
                self.log("Streamlit App is responding", "SUCCESS")
                return True
            else:
                self.log(f"Streamlit App not responding: {response.status_code}", "ERROR")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log(f"Could not reach Streamlit App: {e}", "ERROR")
            return False
    
    def test_nginx_config_syntax(self) -> bool:
        """Test 4: nginx Configuration Syntax"""
        self.log("Testing nginx configuration syntax...")
        
        result = self.run_command("docker compose exec nginx nginx -t")
        if result["success"]:
            self.log("nginx configuration syntax is valid", "SUCCESS")
            return True
        else:
            self.log(f"nginx configuration syntax error: {result.get('stderr', result.get('stdout'))}", "ERROR")
            return False
    
    def test_environment_configuration(self) -> bool:
        """Test 5: Environment Configuration"""
        self.log("Checking environment configuration...")
        
        required_files = [".env", "docker-compose.yml", "nginx/default-auth.conf"]
        missing_files = []
        
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.log(f"Missing configuration files: {missing_files}", "ERROR")
            return False
        
        # Check .env has required variables
        env_file = self.project_root / ".env"
        try:
            env_content = env_file.read_text()
            required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET", "DOMAIN_NAME"]
            missing_vars = []
            
            for var in required_vars:
                if f"{var}=" not in env_content:
                    missing_vars.append(var)
            
            if missing_vars:
                self.log(f"Missing environment variables: {missing_vars}", "ERROR")
                return False
            
            self.log("Environment configuration is complete", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Could not read .env file: {e}", "ERROR")
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test 6: Database Connectivity"""
        self.log("Testing database connectivity...")
        
        # Test via auth service health check (which includes Supabase check)
        try:
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                supabase_status = data.get("services", {}).get("supabase", {})
                if supabase_status.get("status") == "healthy":
                    self.log("Database connectivity confirmed", "SUCCESS")
                    return True
                else:
                    self.log(f"Database connectivity issue: {supabase_status}", "ERROR")
                    return False
            else:
                self.log("Could not check database connectivity", "ERROR")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log(f"Database connectivity test failed: {e}", "ERROR")
            return False
    
    def test_cookie_authentication_flow(self) -> bool:
        """Test 7: End-to-End Cookie Authentication"""
        self.log("Testing end-to-end cookie authentication flow...")
        
        session = requests.Session()
        
        try:
            # Step 1: Test login endpoint
            login_response = session.post(
                "http://localhost:8000/auth/login",
                json={"email": "test@example.com", "password": "wrong_password"},
                timeout=10
            )
            
            if login_response.status_code == 401:
                self.log("Login properly rejects invalid credentials", "SUCCESS")
            else:
                self.log(f"Login validation issue: {login_response.status_code}", "WARNING")
            
            # Step 2: Test session info without cookie
            info_response = session.get("http://localhost:8000/auth/session/info", timeout=10)
            if info_response.status_code == 401:
                self.log("Session info properly requires authentication", "SUCCESS")
            else:
                self.log(f"Session info security issue: {info_response.status_code}", "ERROR")
                return False
            
            # Step 3: Test verify endpoint without cookie
            verify_response = session.get("http://localhost:8000/auth/verify", timeout=10)
            if verify_response.status_code == 401:
                self.log("Verify endpoint properly requires authentication", "SUCCESS")
                return True
            else:
                self.log(f"Verify endpoint security issue: {verify_response.status_code}", "ERROR")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log(f"Authentication flow test failed: {e}", "ERROR")
            return False
    
    def test_system_compatibility(self) -> bool:
        """Test 8: System Compatibility Check"""
        self.log("Testing system compatibility...")
        
        compatibility_issues = []
        
        # Check if old LocalStorage code still exists
        old_auth_patterns = ["localStorage", "sessionStorage", "st.session_state.user"]
        for pattern in old_auth_patterns:
            result = self.run_command(f"grep -r '{pattern}' app/ || true")
            if result["success"] and result["stdout"]:
                compatibility_issues.append(f"Found old auth pattern '{pattern}' in: {result['stdout'][:100]}...")
        
        # Check for conflicting session management
        session_patterns = ["session_state.session", "supabase.auth.sign_in"]
        for pattern in session_patterns:
            result = self.run_command(f"grep -r '{pattern}' app/ || true")
            if result["success"] and result["stdout"]:
                # This is informational, not necessarily an issue
                self.log(f"Found session pattern '{pattern}' - review for compatibility")
        
        if compatibility_issues:
            self.log(f"Compatibility issues found: {len(compatibility_issues)}", "WARNING")
            for issue in compatibility_issues[:3]:  # Show first 3
                self.log(f"  - {issue}", "WARNING")
            return False
        else:
            self.log("No obvious compatibility issues detected", "SUCCESS")
            return True
    
    def test_performance_baseline(self) -> bool:
        """Test 9: Performance Baseline"""
        self.log("Testing performance baseline...")
        
        try:
            # Test auth service response time
            times = []
            for _ in range(5):
                start_time = time.time()
                response = requests.get("http://localhost:8000/health", timeout=10)
                end_time = time.time()
                
                if response.status_code == 200:
                    times.append((end_time - start_time) * 1000)  # Convert to ms
                else:
                    self.log(f"Health check failed during performance test: {response.status_code}", "ERROR")
                    return False
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            self.log(f"Auth Service performance: avg={avg_time:.1f}ms, max={max_time:.1f}ms")
            
            if avg_time > 100:
                self.log(f"Performance concern: Average response time {avg_time:.1f}ms > 100ms", "WARNING")
                return False
            else:
                self.log("Performance baseline acceptable", "SUCCESS")
                return True
                
        except Exception as e:
            self.log(f"Performance test failed: {e}", "ERROR")
            return False
    
    def test_security_configuration(self) -> bool:
        """Test 10: Security Configuration"""
        self.log("Testing security configuration...")
        
        try:
            # Test CORS headers
            response = requests.options("http://localhost:8000/auth/login", timeout=10)
            cors_headers = [h.lower() for h in response.headers.keys()]
            
            required_headers = ["access-control-allow-origin", "access-control-allow-methods"]
            missing_headers = [h for h in required_headers if h not in cors_headers]
            
            if missing_headers:
                self.log(f"Missing CORS headers: {missing_headers}", "WARNING")
            
            # Test that credentials are allowed
            if response.headers.get("access-control-allow-credentials") == "true":
                self.log("CORS credentials properly configured", "SUCCESS")
            else:
                self.log("CORS credentials not configured", "WARNING")
            
            # Check nginx auth configuration exists
            auth_config = self.project_root / "nginx" / "default-auth.conf"
            if auth_config.exists():
                config_content = auth_config.read_text()
                if "auth_request" in config_content:
                    self.log("nginx auth_request configuration found", "SUCCESS")
                    return True
                else:
                    self.log("nginx auth_request not configured", "ERROR")
                    return False
            else:
                self.log("nginx auth configuration missing", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Security configuration test failed: {e}", "ERROR")
            return False
    
    def run_integration_tests(self):
        """Führt alle Integrationstests aus"""
        print(f"\n{BOLD}=== GUSTAV System Integration Test Suite ==={RESET}")
        print(f"Project Root: {self.project_root}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        tests = [
            ("Docker Services Status", self.test_docker_services),
            ("Auth Service Health", self.test_auth_service_health),
            ("Streamlit App Health", self.test_streamlit_app_health),
            ("nginx Configuration", self.test_nginx_config_syntax),
            ("Environment Configuration", self.test_environment_configuration),
            ("Database Connectivity", self.test_database_connectivity),
            ("Cookie Authentication Flow", self.test_cookie_authentication_flow),
            ("System Compatibility", self.test_system_compatibility),
            ("Performance Baseline", self.test_performance_baseline),
            ("Security Configuration", self.test_security_configuration),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                print(f"\n{BLUE}Running: {test_name}{RESET}")
                start_time = time.time()
                success = test_func()
                duration = time.time() - start_time
                
                results.append({
                    "name": test_name,
                    "success": success,
                    "duration": duration
                })
                
                if success:
                    print(f"{GREEN}✓ {test_name} - PASSED ({duration:.2f}s){RESET}")
                else:
                    print(f"{RED}✗ {test_name} - FAILED ({duration:.2f}s){RESET}")
                    
            except Exception as e:
                print(f"{RED}✗ {test_name} - ERROR: {str(e)}{RESET}")
                results.append({
                    "name": test_name,
                    "success": False,
                    "error": str(e)
                })
        
        # Summary
        self.print_integration_summary(results)
    
    def print_integration_summary(self, results: List[Dict[str, Any]]):
        """Zeigt eine umfassende Zusammenfassung der Integrationstests"""
        print(f"\n{BOLD}=== INTEGRATION TEST SUMMARY ==={RESET}")
        
        total = len(results)
        passed = sum(1 for r in results if r["success"])
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        
        if failed > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for result in results:
                if not result["success"]:
                    error_info = result.get("error", "Test returned False")
                    print(f"  - {result['name']}: {error_info}")
        
        # Integration Readiness Assessment
        print(f"\n{BOLD}=== INTEGRATION READINESS ASSESSMENT ==={RESET}")
        
        critical_tests = [
            "Docker Services Status",
            "Auth Service Health", 
            "Database Connectivity",
            "Cookie Authentication Flow"
        ]
        
        critical_failures = [
            r["name"] for r in results 
            if not r["success"] and r["name"] in critical_tests
        ]
        
        if not critical_failures and passed >= total * 0.8:
            print(f"{GREEN}🎯 READY FOR INTEGRATION{RESET}")
            print("Das HttpOnly Cookie Authentication System ist bereit für die nahtlose Integration.")
            print("\n✅ Alle kritischen Komponenten funktionieren")
            print("✅ Auth Service läuft stabil")
            print("✅ Konfiguration ist vollständig")
            print("✅ Sicherheitsfeatures sind aktiv")
            
        elif critical_failures:
            print(f"{RED}❌ NICHT BEREIT FÜR INTEGRATION{RESET}")
            print("Kritische Probleme müssen behoben werden:")
            for failure in critical_failures:
                print(f"  - {failure}")
                
        else:
            print(f"{YELLOW}⚠️  BEDINGT BEREIT FÜR INTEGRATION{RESET}")
            print("System funktioniert grundsätzlich, aber es gibt kleinere Probleme:")
            failed_tests = [r["name"] for r in results if not r["success"]]
            for failure in failed_tests:
                print(f"  - {failure}")
        
        # Next Steps
        print(f"\n{BOLD}=== EMPFOHLENE NÄCHSTE SCHRITTE ==={RESET}")
        
        if critical_failures:
            print("1. Kritische Probleme beheben (siehe oben)")
            print("2. Tests erneut ausführen")
            print("3. Erst nach erfolgreichen Tests mit Integration fortfahren")
        elif failed > 0:
            print("1. Kleinere Probleme optional beheben")
            print("2. Mit nginx auth_request Konfiguration fortfahren")
            print("3. Streamlit Integration implementieren")
            print("4. End-to-End Tests mit echten Benutzern")
        else:
            print("1. nginx auth_request aktivieren (docker-compose.yml anpassen)")
            print("2. Streamlit Integration implementieren")
            print("3. End-to-End Tests durchführen")
            print("4. Produktions-Rollout vorbereiten")
        
        print(f"\n{BOLD}=== SYSTEM STATUS ==={RESET}")
        if passed == total:
            print(f"{GREEN}All systems operational ✅{RESET}")
        elif critical_failures:
            print(f"{RED}System has critical issues ❌{RESET}")
        else:
            print(f"{YELLOW}System operational with minor issues ⚠️{RESET}")
        
        return failed == 0


def main():
    """Hauptfunktion"""
    tester = SystemIntegrationTester()
    
    # Verify we're in the right directory
    if not tester.project_root.exists():
        print(f"{RED}Project directory not found: {tester.project_root}{RESET}")
        sys.exit(1)
    
    # Run tests
    success = tester.run_integration_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()