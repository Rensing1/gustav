# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Tests for security utilities and validators.
"""

import pytest
from utils.validators import (
    validate_course_name, 
    sanitize_filename, 
    validate_file_upload,
    validate_url,
    validate_email,
    ValidationError
)
from utils.security import hash_id, security_log, hash_ip, get_safe_error_message


class TestInputValidation:
    """Tests input validation against known attacks."""
    
    def test_course_name_sql_injection(self):
        """Test against SQL Injection in course names."""
        malicious_inputs = [
            "'; DROP TABLE courses; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM courses WHERE 1=1",
            "' UNION SELECT * FROM users--",
        ]
        
        for malicious in malicious_inputs:
            with pytest.raises(ValidationError):
                validate_course_name(malicious)
    
    def test_course_name_xss(self):
        """Test against XSS in course names."""
        xss_attempts = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "<svg onload=alert('xss')>",
            "';alert(String.fromCharCode(88,83,83))//",
        ]
        
        for xss in xss_attempts:
            with pytest.raises(ValidationError):
                validate_course_name(xss)
    
    def test_path_traversal_prevention(self):
        """Test against Path Traversal."""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "file://etc/passwd",
            "\x00malicious.pdf",  # Null byte
            "../../../../../../../../etc/passwd",
            ".././.././../etc/passwd",
            "....//....//....//etc/passwd",
        ]
        
        for attempt in path_traversal_attempts:
            safe = sanitize_filename(attempt)
            assert ".." not in safe
            assert "/" not in safe
            assert "\\" not in safe
            assert "\x00" not in safe
    
    def test_valid_course_names(self):
        """Test with valid course names."""
        valid_names = [
            "Mathematik 8a",
            "Bio-Chemie AG",
            "Französisch für Anfänger",
            "Sport-Leistungskurs",
            "Deutsch - Grundkurs 11",
        ]
        
        for name in valid_names:
            assert validate_course_name(name) == name.strip()
    
    def test_filename_sanitization(self):
        """Test filename sanitization."""
        test_cases = [
            ("normal_file.pdf", "normal_file.pdf"),
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("Ümläütë.docx", "_ml__t_.docx"),
            (".hidden_file", "_hidden_file"),
            ("file/../../../etc/passwd", "passwd"),
            ("file\x00.txt", "file.txt"),
            ("very" * 50 + ".txt", "very" * 25),  # Truncated to 100 chars
        ]
        
        for input_name, expected in test_cases:
            assert sanitize_filename(input_name) == expected
    
    def test_url_validation(self):
        """Test URL validation."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8000",
            "https://sub.domain.com/path?query=value",
            "https://192.168.1.1",
        ]
        
        invalid_urls = [
            "javascript:alert('xss')",
            "file:///etc/passwd",
            "ftp://example.com",
            "not a url at all",
            "https://",
            "",
        ]
        
        for url in valid_urls:
            assert validate_url(url) == url.strip()
        
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                validate_url(url)
    
    def test_email_validation(self):
        """Test email validation."""
        valid_emails = [
            "user@example.com",
            "first.last@school.edu",
            "test+tag@domain.co.uk",
        ]
        
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user @example.com",
            "",
        ]
        
        for email in valid_emails:
            assert validate_email(email) == email.strip().lower()
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                validate_email(email)


class TestPIIHashing:
    """Tests PII hashing for logs."""
    
    def test_hash_consistency(self):
        """Same IDs produce same hashes."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        hash1 = hash_id(user_id)
        hash2 = hash_id(user_id)
        
        assert hash1 == hash2
        assert len(hash1) == 8
        assert user_id not in hash1
    
    def test_hash_empty_values(self):
        """Empty values return NONE."""
        assert hash_id("") == "NONE"
        assert hash_id(None) == "NONE"
    
    def test_hash_ip(self):
        """Test IP address hashing."""
        ip = "192.168.1.100"
        hashed = hash_ip(ip)
        
        assert len(hashed) == 8
        assert ip not in hashed
        assert hash_ip("") == "NONE"
    
    def test_different_inputs_different_hashes(self):
        """Different inputs produce different hashes."""
        id1 = "user-123"
        id2 = "user-124"
        
        assert hash_id(id1) != hash_id(id2)


class TestSafeErrorMessages:
    """Tests safe error message generation."""
    
    def test_user_facing_errors(self):
        """Test user-facing error messages."""
        class IntegrityError(Exception):
            pass
        
        class PermissionError(Exception):
            pass
        
        error = IntegrityError("UNIQUE constraint failed: users.email")
        msg = get_safe_error_message(error, user_facing=True)
        assert msg == "Ein Eintrag mit diesen Daten existiert bereits."
        assert "users.email" not in msg
        
        error = PermissionError("User 123 cannot access course 456")
        msg = get_safe_error_message(error, user_facing=True)
        assert msg == "Sie haben keine Berechtigung für diese Aktion."
        assert "123" not in msg
        assert "456" not in msg
    
    def test_logging_errors(self):
        """Test logging error messages."""
        error = ValueError("Invalid input: user@example.com")
        msg = get_safe_error_message(error, user_facing=False)
        assert "ValueError" in msg
        assert "Invalid input" in msg


class MockFile:
    """Mock file object for testing."""
    def __init__(self, name, size=1000, type="application/pdf"):
        self.name = name
        self.size = size
        self.type = type


class TestFileUploadValidation:
    """Tests file upload validation."""
    
    def test_valid_files(self):
        """Test valid file uploads."""
        valid_files = [
            MockFile("document.pdf"),
            MockFile("image.jpg", 1024 * 1024),  # 1MB
            MockFile("photo.png"),
            MockFile("report.docx"),
        ]
        
        for file in valid_files:
            validate_file_upload(file)  # Should not raise
    
    def test_invalid_file_types(self):
        """Test invalid file types."""
        invalid_files = [
            MockFile("script.exe"),
            MockFile("virus.bat"),
            MockFile("hack.sh"),
            MockFile("data.zip"),
        ]
        
        for file in invalid_files:
            with pytest.raises(ValidationError) as exc_info:
                validate_file_upload(file)
            assert "nicht erlaubt" in str(exc_info.value)
    
    def test_file_too_large(self):
        """Test file size limit."""
        large_file = MockFile("huge.pdf", 100 * 1024 * 1024)  # 100MB
        
        with pytest.raises(ValidationError) as exc_info:
            validate_file_upload(large_file)
        assert "zu groß" in str(exc_info.value)