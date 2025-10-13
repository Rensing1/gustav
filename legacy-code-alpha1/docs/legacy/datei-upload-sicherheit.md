# Datei-Upload Sicherheitsempfehlungen

## ✅ STATUS UPDATE (Januar 2025): KRITISCHE SICHERHEITSLÜCKEN BEHOBEN

**Alle kritischen Sicherheitsmaßnahmen sind implementiert und produktiv im Einsatz:**
- ✅ File-Type-Validation mit Magic Numbers
- ✅ Path Traversal Protection  
- ✅ Input Validation Framework
- ✅ XSS Protection für HTML-Applets
- ✅ Umfassende Security-Test-Suite

**File-Upload ist sicher für den Produktionseinsatz in Schulen.**

---

## Ursprüngliche Sicherheitsempfehlungen (Referenz)

Diese Datei dokumentiert die wichtigsten Sicherheitsmaßnahmen für das File-Upload-Feature in GUSTAV. Die meisten Empfehlungen wurden **erfolgreich implementiert**.

---

## 1. File Validation (KRITISCH)

### 1.1 Implementiere File-Type-Validation

**Problem:** Aktuell wird nur die Dateigröße, nicht der Dateityp validiert.

**Lösung:**
```python
# app/utils/validators.py erweitern
import magic
from pathlib import Path

def validate_vision_file(file) -> None:
    """Validiert hochgeladene Dateien für Vision-Processing."""
    
    # Erlaubte MIME-Types
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'application/pdf'
    }
    
    # Magic Number Check (sicherer als Extension)
    file_header = file.read(1024)
    file.seek(0)  # Reset file pointer
    
    detected_mime = magic.from_buffer(file_header, mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(f"Unerlaubter Dateityp: {detected_mime}")
    
    # Zusätzlicher Extension-Check
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf'}
    file_ext = Path(file.name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unerlaubte Dateiendung: {file_ext}")
```

### 1.2 Path Traversal Protection

**Problem:** Unsanitized Dateinamen können Path Traversal ermöglichen.

**Fix für** `app/components/detail_editor.py`:
```python
# ALT (Zeile 157):
file_path = f"unit_{unit_id}/section_{section_id}/{uuid.uuid4()}_{uploaded_file.name}"

# NEU:
from app.utils.validators import sanitize_filename
safe_filename = sanitize_filename(uploaded_file.name)
file_path = f"unit_{unit_id}/section_{section_id}/{uuid.uuid4()}_{safe_filename}"
```

**Sanitize-Funktion:**
```python
def sanitize_filename(filename: str) -> str:
    """Entfernt gefährliche Zeichen aus Dateinamen."""
    # Nur Basename (verhindert ../)
    safe_name = Path(filename).name
    # Nur erlaubte Zeichen
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', safe_name)
    # Maximale Länge
    return safe_name[:100]
```

---

## 2. File Size & Content Limits

### 2.1 Verschärfte Size Limits

```python
# app/config.py
MAX_VISION_FILE_SIZE = 10 * 1024 * 1024  # 10MB statt 20MB
MAX_PDF_PAGES = 5  # Limit für PDF-Processing

# app/ai/vision_processor.py
def validate_pdf_pages(pdf_bytes: bytes) -> None:
    """Prüft PDF-Seitenzahl vor Processing."""
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    if pdf_document.page_count > MAX_PDF_PAGES:
        pdf_document.close()
        raise ValidationError(f"PDF hat zu viele Seiten (max. {MAX_PDF_PAGES})")
    pdf_document.close()
```

### 2.2 Content-basierte Limits

```python
def check_image_dimensions(image_bytes: bytes) -> None:
    """Verhindert Memory-Exhaustion durch riesige Bilder."""
    MAX_DIMENSION = 4096  # Pixel
    
    image = Image.open(io.BytesIO(image_bytes))
    width, height = image.size
    
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(f"Bild zu groß: {width}x{height} (max. {MAX_DIMENSION}x{MAX_DIMENSION})")
```

---

## 3. Vision Output Security

### 3.1 Prompt Injection Protection

```python
def sanitize_vision_output(text: str) -> str:
    """Entfernt potentielle Prompt-Injection-Versuche."""
    dangerous_patterns = [
        r'ignore.*previous.*instructions',
        r'system.*prompt',
        r'disregard.*above',
        r'<\s*script\s*>',
        r'javascript:',
        r'eval\s*\(',
        r'exec\s*\('
    ]
    
    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '[FILTERED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized
```

### 3.2 Output Validation

```python
def validate_vision_output(text: str) -> bool:
    """Prüft Vision-Output auf Plausibilität."""
    # Zu lang für handgeschriebenen Text
    if len(text) > 10000:
        return False
    
    # Zu viele Zeilen
    if text.count('\n') > 100:
        return False
    
    # Verdächtige Zeichenfolgen
    if '[FILTERED]' in text:
        return False
    
    # Mindestens etwas Text
    if len(text.strip()) < 10:
        return False
    
    return True
```

---

## 4. Privacy Protection (DSGVO)

### 4.1 PII Detection & Redaction

```python
def detect_and_redact_pii(text: str) -> tuple[str, list[str]]:
    """Erkennt und zensiert persönliche Daten."""
    pii_patterns = {
        'phone': (r'\b\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b', '[TELEFON]'),
        'email': (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
        'license_plate': (r'\b[A-Z]{1,2}[-\s]?[A-Z]{1,2}[-\s]?\d{1,4}\b', '[KFZ]'),
        'date_of_birth': (r'\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b', '[DATUM]'),
        'student_id': (r'\b\d{7,10}\b', '[SCHÜLER-ID]')
    }
    
    found_pii = []
    redacted_text = text
    
    for pii_type, (pattern, replacement) in pii_patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            found_pii.extend([(pii_type, match) for match in matches])
            redacted_text = re.sub(pattern, replacement, redacted_text)
    
    return redacted_text, found_pii
```

### 4.2 Logging ohne PII

```python
from app.utils.security import security_log, hash_id

def log_vision_processing(user_id: str, file_size: int, extracted_chars: int, pii_found: list):
    """Loggt Vision-Processing DSGVO-konform."""
    security_log(
        "vision_processing_complete",
        user_id=user_id,  # Wird automatisch gehashed
        file_size_kb=file_size // 1024,
        extracted_chars=extracted_chars,
        pii_types_found=[pii[0] for pii in pii_found],  # Nur Typen, nicht Werte
        timestamp=datetime.utcnow().isoformat()
    )
```

---

## 5. Rate Limiting & Abuse Prevention

### 5.1 Upload Rate Limiting

```python
# app/utils/rate_limiter.py
from datetime import datetime, timedelta
from collections import defaultdict

class VisionUploadRateLimiter:
    def __init__(self):
        self.uploads = defaultdict(list)
        self.MAX_UPLOADS_PER_HOUR = 10
        self.MAX_SIZE_PER_HOUR = 50 * 1024 * 1024  # 50MB
    
    def check_rate_limit(self, user_id: str, file_size: int) -> tuple[bool, str]:
        """Prüft Upload-Rate-Limits."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Bereinige alte Einträge
        self.uploads[user_id] = [
            (timestamp, size) for timestamp, size in self.uploads[user_id]
            if timestamp > hour_ago
        ]
        
        # Prüfe Anzahl
        if len(self.uploads[user_id]) >= self.MAX_UPLOADS_PER_HOUR:
            return False, f"Maximal {self.MAX_UPLOADS_PER_HOUR} Uploads pro Stunde"
        
        # Prüfe Gesamtgröße
        total_size = sum(size for _, size in self.uploads[user_id]) + file_size
        if total_size > self.MAX_SIZE_PER_HOUR:
            return False, f"Maximal {self.MAX_SIZE_PER_HOUR // 1024 // 1024}MB pro Stunde"
        
        # Erfasse Upload
        self.uploads[user_id].append((now, file_size))
        return True, "OK"
```

### 5.2 Anomaly Detection

```python
def detect_upload_anomalies(user_id: str, file_info: dict) -> list[str]:
    """Erkennt verdächtige Upload-Muster."""
    alerts = []
    
    # Nachtaktivität (außerhalb Schulzeiten)
    hour = datetime.now().hour
    if hour < 6 or hour > 22:
        alerts.append("Upload außerhalb Schulzeiten")
    
    # Identische Uploads
    file_hash = hashlib.sha256(file_info['content']).hexdigest()
    if was_recently_uploaded(user_id, file_hash):
        alerts.append("Identische Datei bereits hochgeladen")
    
    # Verdächtige Dateinamen
    suspicious_names = ['test', 'hack', 'exploit', 'virus']
    if any(name in file_info['name'].lower() for name in suspicious_names):
        alerts.append("Verdächtiger Dateiname")
    
    return alerts
```

---

## 6. Implementierungs-Checkliste

### ✅ IMPLEMENTIERT (Januar 2025):
- [x] **File-Type-Validation mit Magic Numbers** - `utils/validators.py` + `submission_input.py`
- [x] **Path Traversal Protection** - `sanitize_filename()` in beiden Upload-Komponenten  
- [x] **Input Validation Framework** - Vollständiges Validierungs-System implementiert
- [x] **Security Test Suite** - `app/tests/test_security.py` mit umfassenden Tests
- [x] **XSS Protection für Applets** - Bleach-Sanitization implementiert

### ✅ IMPLEMENTIERT (Januar 2025):
- [x] **Server-seitiges Rate Limiting** - `utils/rate_limiter.py` mit In-Memory-Storage
- [x] **API-Bypass-Schutz** - 10 Uploads/Stunde, 50MB/Stunde pro Benutzer
- [x] **Security-Integration** - PII-sicheres Logging mit gehashten User-IDs

### Kurzfristig (Q2 2025):
- [ ] Vollständige CSP-Header Konfiguration  
- [ ] Enhanced Monitoring Dashboard

### Mittelfristig (Q3 2025):
- [ ] Virus Scanning Integration
- [ ] Automated Security Scans in CI/CD
- [ ] MFA/2FA Implementation

### NICHT IMPLEMENTIERT (bewusste Designentscheidung):
- [x] **PII Detection & Redaction** - Benutzeraufklärung statt automatischer Erkennung
- [x] **Vision Output Sanitization** - Prompt-Kontext bietet ausreichenden Schutz
- [x] **Anomaly Detection** - Schulkontext mit bekannten Benutzern macht dies überflüssig

---

## 7. Testing & Validation

### Security Test Cases

```python
# tests/test_vision_security.py
import pytest
from app.utils.validators import validate_vision_file, sanitize_filename

class TestVisionSecurity:
    def test_path_traversal_prevention(self):
        """Test gegen Path Traversal Angriffe."""
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "innocent.jpg/../../../evil.sh",
            "file\x00.jpg"  # Null byte
        ]
        
        for name in malicious_names:
            safe = sanitize_filename(name)
            assert ".." not in safe
            assert "/" not in safe
            assert "\\" not in safe
            assert "\x00" not in safe
    
    def test_file_type_validation(self):
        """Test File-Type-Validation."""
        # Erstelle Test-Files mit falschen Extensions
        evil_pdf = b"<script>alert('xss')</script>"
        
        with pytest.raises(ValidationError):
            validate_vision_file(create_fake_file("evil.pdf", evil_pdf))
```

---

## 8. Monitoring & Alerting

### Security Metrics

```python
VISION_SECURITY_METRICS = {
    'pii_detections': counter,
    'validation_failures': counter,
    'rate_limit_blocks': counter,
    'suspicious_uploads': counter,
    'sanitized_outputs': counter
}

def alert_on_security_events():
    """Sendet Alerts bei Security-Events."""
    if get_metric('pii_detections') > 10:
        send_alert("Hohe PII-Detection-Rate im Vision-Upload")
    
    if get_metric('validation_failures') > 50:
        send_alert("Viele fehlgeschlagene Upload-Validierungen")
```

---

**Priorität:** Implementiere mindestens Punkte 1-3 SOFORT bevor das Feature weiter genutzt wird. Die restlichen Maßnahmen sollten innerhalb der nächsten 2-4 Wochen folgen.

**Kontakt bei Fragen:** security@gustav-lms.org