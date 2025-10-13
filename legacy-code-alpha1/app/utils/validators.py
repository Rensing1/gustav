# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Input validation utilities for GUSTAV.

Provides functions for validating and sanitizing user input to prevent
security vulnerabilities like SQL injection, XSS, and path traversal.
"""

import re
from pathlib import Path
from typing import Optional


class ValidationError(ValueError):
    """Spezifische Exception für Validierungsfehler."""
    pass


def validate_course_name(name: str) -> str:
    """Validiert Kursnamen nach Sicherheitsrichtlinien.
    
    Args:
        name: The course name to validate
        
    Returns:
        The validated and stripped course name
        
    Raises:
        ValidationError: If the course name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Kursname darf nicht leer sein")
    
    # Allow German umlauts, alphanumeric, spaces, hyphens
    if not re.match(r'^[a-zA-Z0-9äöüÄÖÜß\s\-]{3,50}$', name):
        raise ValidationError(
            "Kursname darf nur Buchstaben, Zahlen, Leerzeichen und Bindestriche enthalten (3-50 Zeichen)"
        )
    
    return name.strip()


def sanitize_filename(filename: str) -> str:
    """Entfernt gefährliche Zeichen aus Dateinamen.
    
    Prevents path traversal attacks by sanitizing filenames.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        A safe filename with dangerous characters removed
    """
    # Use only the basename (prevents path traversal)
    safe_name = Path(filename).name
    
    # Remove null bytes
    safe_name = safe_name.replace('\x00', '')
    
    # Only allow safe characters
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', safe_name)
    
    # Ensure it doesn't start with a dot (hidden file)
    if safe_name.startswith('.'):
        safe_name = '_' + safe_name[1:]
    
    # Maximum length
    return safe_name[:100]


def validate_file_upload(file) -> None:
    """Validiert hochgeladene Dateien.
    
    Checks file type and size to prevent malicious uploads.
    
    Args:
        file: The uploaded file object (e.g., from Streamlit)
        
    Raises:
        ValidationError: If the file is invalid
    """
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.txt', '.mp4', '.mp3'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (matching current limit)
    
    if not file:
        raise ValidationError("Keine Datei ausgewählt")
    
    # Check file size
    if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
        raise ValidationError(f"Datei zu groß (max. {MAX_FILE_SIZE // 1024 // 1024}MB)")
    
    # Check file extension
    file_ext = Path(file.name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Dateityp {file_ext} nicht erlaubt. Erlaubte Typen: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_url(url: str) -> str:
    """Validates and sanitizes URLs.
    
    Args:
        url: The URL to validate
        
    Returns:
        The validated URL
        
    Raises:
        ValidationError: If the URL is invalid
    """
    if not url or not url.strip():
        raise ValidationError("URL darf nicht leer sein")
    
    url = url.strip()
    
    # Basic URL pattern check
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        raise ValidationError("Ungültige URL. Bitte geben Sie eine vollständige URL mit http:// oder https:// ein")
    
    return url


def validate_email(email: str) -> str:
    """Validates email addresses.
    
    Args:
        email: The email to validate
        
    Returns:
        The validated email (lowercase)
        
    Raises:
        ValidationError: If the email is invalid
    """
    if not email or not email.strip():
        raise ValidationError("E-Mail-Adresse darf nicht leer sein")
    
    email = email.strip().lower()
    
    # Simple email pattern
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    if not email_pattern.match(email):
        raise ValidationError("Ungültige E-Mail-Adresse")
    
    return email


def validate_unit_name(name: str) -> str:
    """Validates unit names.
    
    Args:
        name: The unit name to validate
        
    Returns:
        The validated unit name
        
    Raises:
        ValidationError: If the unit name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Einheitsname darf nicht leer sein")
    
    # Similar to course name but allows more characters
    if not re.match(r'^[a-zA-Z0-9äöüÄÖÜß\s\-\.\,\(\)]{2,100}$', name):
        raise ValidationError(
            "Einheitsname enthält ungültige Zeichen (2-100 Zeichen erlaubt)"
        )
    
    return name.strip()


def validate_section_name(name: str) -> str:
    """Validates section names.
    
    Args:
        name: The section name to validate
        
    Returns:
        The validated section name
        
    Raises:
        ValidationError: If the section name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Abschnittsname darf nicht leer sein")
    
    # Similar to unit name validation
    if not re.match(r'^[a-zA-Z0-9äöüÄÖÜß\s\-\.\,\(\)]{2,100}$', name):
        raise ValidationError(
            "Abschnittsname enthält ungültige Zeichen (2-100 Zeichen erlaubt)"
        )
    
    return name.strip()


def validate_task_instruction(instruction: str) -> str:
    """Validates task instructions.
    
    Args:
        instruction: The task instruction to validate
        
    Returns:
        The validated instruction
        
    Raises:
        ValidationError: If the instruction is invalid
    """
    if not instruction or not instruction.strip():
        raise ValidationError("Aufgabenstellung darf nicht leer sein")
    
    instruction = instruction.strip()
    
    if len(instruction) < 10:
        raise ValidationError("Aufgabenstellung muss mindestens 10 Zeichen lang sein")
    
    if len(instruction) > 5000:
        raise ValidationError("Aufgabenstellung darf maximal 5000 Zeichen lang sein")
    
    return instruction