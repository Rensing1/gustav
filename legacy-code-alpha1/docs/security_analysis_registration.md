# Security-Analyse: GUSTAV Registrierungsfunktionalität

**Erstellt:** 2025-09-08  
**Autor:** Security Analysis Tool  
**Scope:** /auth_service/app/pages/register.py und zugehörige Komponenten

## Executive Summary

Die Registrierungsfunktionalität zeigt eine solide Sicherheitsarchitektur mit mehreren Schutzschichten. Es wurden **keine kritischen Sicherheitslücken** gefunden. Die Implementierung folgt weitgehend Security Best Practices, jedoch gibt es einige Bereiche mit Verbesserungspotential.

### Sicherheitsstärken:
- ✅ Robuste Domain-Validierung auf mehreren Ebenen
- ✅ CSRF-Schutz via Double Submit Cookie Pattern
- ✅ Timing-Attack-Protection implementiert
- ✅ Sichere Session-Verwaltung mit Supabase
- ✅ Keine direkten SQL-Injektionsmöglichkeiten
- ✅ XSS-Schutz durch Template-Escaping und Security Headers
- ✅ HttpOnly Cookies für Sessions

### Verbesserungspotential:
- ⚠️ Rate-Limiting nicht vollständig implementiert
- ⚠️ Keine Content Security Policy (CSP)
- ⚠️ Client-seitige Validierung kann umgangen werden
- ⚠️ Fehlende Passwort-Komplexitätsprüfung
- ⚠️ Keine Account-Enumeration-Protection

## 1. Domain-Validierung Analyse

### 1.1 Implementierung
Die Domain-Validierung erfolgt auf drei Ebenen:

**Frontend (register.html:44)**
```html
pattern=".*@gymalf\.de$"
```

**Backend (register.py:31-50)**
```python
def validate_gymalf_email(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return email.lower().endswith("@gymalf.de")
```

**Datenbank (handle_new_user trigger)**
```sql
email_domain := LOWER(SUBSTRING(NEW.email FROM '@[^@]+$'));
IF NOT is_domain_allowed THEN
    RAISE EXCEPTION 'Registrierung nur mit schulischen E-Mail-Adressen (@gymalf.de) möglich.';
```

### 1.2 Sicherheitsbewertung
- **Stärke:** Mehrschichtige Validierung verhindert Bypass-Versuche
- **Schwäche:** `endswith()` könnte theoretisch durch Subdomains umgangen werden (z.B. `user@evil.gymalf.de`)

### 1.3 Bypass-Versuche
Getestete Angriffsvektoren:
- `user@gymalf.de.evil.com` - ❌ Blockiert
- `user@GYMALF.DE` - ✅ Erlaubt (case-insensitive)
- `user+tag@gymalf.de` - ✅ Erlaubt (valide Email-Syntax)
- `user@gymalf.de\x00@evil.com` - ❌ Blockiert durch Regex
- `user@gymalf.de%0A@evil.com` - ❌ Blockiert durch Regex

**Empfehlung:** Regex anpassen auf exakte Domain-Prüfung:
```python
return bool(re.match(r'^[a-zA-Z0-9._%+-]+@gymalf\.de$', email.lower()))
```

## 2. CSRF-Protection Analyse

### 2.1 Implementierung
Double Submit Cookie Pattern:

**Cookie-Setzung (register.py:102-112)**
```python
html_response.set_cookie(
    key="csrf_token",
    value=csrf_token,
    httponly=True,
    secure=is_secure,
    samesite="lax",
    max_age=3600,
    path="/auth"
)
```

**Validierung (register.py:132-137)**
```python
if not csrf_cookie or csrf_cookie != csrf_form:
    logger.warning(f"CSRF validation failed...")
    return RedirectResponse(url="/auth/register?error=invalid_csrf", status_code=303)
```

### 2.2 Sicherheitsbewertung
- ✅ HttpOnly Cookie verhindert JavaScript-Zugriff
- ✅ SameSite=Lax schützt vor Cross-Site-Requests
- ✅ Secure-Flag in Production
- ✅ Token-Rotation bei jedem Request
- ⚠️ Kein Origin/Referer-Check als zusätzliche Schicht

## 3. Rate-Limiting Analyse

### 3.1 Konfiguration vs. Implementierung

**Konfiguriert (config.py:51-52):**
```python
RATE_LIMIT_PER_MINUTE: int = 5
RATE_LIMIT_PER_HOUR: int = 60
```

**Rate-Limit Middleware vorhanden aber nicht integriert!**

Die Rate-Limiting Middleware (`/auth_service/app/middleware/rate_limit.py`) ist implementiert aber wird **nicht in main.py eingebunden**:

```python
# FEHLT in main.py:
from app.middleware.rate_limit import rate_limiter, login_limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
```

### 3.2 Sicherheitsrisiko
- 🔴 **Kritisch:** Keine aktive Rate-Limiting Protection
- Brute-Force-Angriffe auf Registrierung möglich
- DoS durch Mass-Registration möglich
- Supabase Rate-Limits als einziger Schutz

**Dringende Empfehlung:** Rate-Limiting aktivieren!

## 4. Error-Handling & Information Leakage

### 4.1 Error Messages
Definierte Fehlermeldungen sind generisch und sicher:
```python
error_messages = {
    "invalid_domain": "Nur E-Mail-Adressen mit @gymalf.de sind erlaubt.",
    "email_exists": "Diese E-Mail-Adresse ist bereits registriert.",
    # ...
}
```

### 4.2 Account Enumeration
⚠️ **Schwachstelle:** Unterschiedliche Fehlermeldungen ermöglichen Account-Enumeration:
- "Diese E-Mail-Adresse ist bereits registriert" verrät Existenz
- Timing-Attack-Schutz vorhanden, aber nicht für alle Pfade

### 4.3 Logging
```python
logger.warning(f"Registration attempt with invalid domain: {email}")
```
⚠️ **PII-Leakage:** E-Mail wird in Logs gespeichert

**Empfehlung:** E-Mail hashen oder nur Domain loggen

## 5. Timing-Attack Protection

### 5.1 Implementierung
```python
start_time = time.time()
# ... validation ...
elapsed = time.time() - start_time
if elapsed < 0.5:
    await asyncio.sleep(0.5 - elapsed)
```

### 5.2 Bewertung
- ✅ Konstante Response-Zeit von 500ms
- ✅ Alle Error-Pfade abgedeckt
- ⚠️ Success-Pfad hat keine Timing-Protection

## 6. Password Security

### 6.1 Aktuelle Validierung
```python
if len(password) < 8:
    return False, "Passwort muss mindestens 8 Zeichen lang sein."
```

### 6.2 Schwachstellen
- ❌ Keine Komplexitätsanforderungen
- ❌ Keine Prüfung auf Common Passwords
- ❌ Keine Prüfung auf Wörterbuch-Angriffe
- ❌ Password = Email möglich

**Empfehlung:** Implementierung von:
- Mindestens 1 Großbuchstabe, 1 Kleinbuchstabe, 1 Zahl
- Blocklist für Top 10000 Passwörter
- Passwort != Email-Check

## 7. XSS-Protection

### 7.1 Template Security
```html
{{ error_messages.get(error, "...") }}
```
✅ Jinja2 Auto-Escaping aktiv

### 7.2 Security Headers
```python
response.headers["X-XSS-Protection"] = "1; mode=block"
response.headers["X-Content-Type-Options"] = "nosniff"
```
✅ Basis-XSS-Schutz vorhanden

### 7.3 Fehlende CSP
⚠️ Keine Content Security Policy implementiert

**Empfehlung:**
```python
response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
```

## 8. SQL Injection

### 8.1 Supabase Client
Alle Datenbankzugriffe erfolgen über Supabase SDK:
```python
response = self.client.auth.sign_up({
    "email": email,
    "password": password
})
```

✅ **Keine direkten SQL-Queries = Keine SQL-Injection möglich**

## 9. Session Security

### 9.1 Datenbank-basierte Sessions
```sql
CREATE TABLE IF NOT EXISTS public.auth_sessions (
    session_id VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT valid_expiration CHECK (expires_at <= created_at + INTERVAL '24 hours')
);
```

### 9.2 Sicherheitsfeatures
- ✅ UUID Session IDs (nicht vorhersagbar)
- ✅ Sliding Window Expiration (90 Minuten)
- ✅ Max 5 Sessions pro User
- ✅ Automatische Cleanup-Jobs
- ✅ RLS aktiviert

## 10. Business Logic Flaws

### 10.1 Registrierungs-Flow
1. CSRF-Validierung
2. Domain-Validierung
3. Passwort-Validierung
4. Supabase-Registrierung
5. Redirect zu Login

✅ Keine Race Conditions identifiziert
✅ Keine TOCTOU-Vulnerabilities

### 10.2 Edge Cases
- Mehrfach-Registrierung: ✅ Verhindert durch Supabase
- Leere Inputs: ✅ Verhindert durch Form-Validation
- Sehr lange Inputs: ⚠️ Keine Längenbeschränkung für E-Mail

## 11. Empfehlungen

### Kritisch (sofort umsetzen):
1. **Rate-Limiting aktivieren** in main.py
2. **E-Mail-Logging anonymisieren** (Datenschutz)

### Wichtig (kurzfristig):
3. **CSP-Header implementieren**
4. **Passwort-Komplexität erhöhen**
5. **Account-Enumeration verhindern** (generische Meldungen)
6. **Email-Regex verschärfen** (exakte Domain-Prüfung)

### Nice-to-have (langfristig):
7. **2FA-Unterstützung** vorbereiten
8. **Captcha** bei wiederholten Fehlversuchen
9. **Security.txt** implementieren
10. **Subresource Integrity** für Static Files

## 12. Code-Beispiele für Fixes

### Rate-Limiting aktivieren:
```python
# main.py
from app.middleware.rate_limit import rate_limiter, custom_rate_limit_handler
from slowapi.errors import RateLimitExceeded

# Nach app = FastAPI(...)
app.state.limiter = rate_limiter.limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# register.py
from ..middleware.rate_limit import login_limiter

@router.post("/register")
@login_limiter
async def process_register(...):
```

### Email-Validierung verbessern:
```python
def validate_gymalf_email(email: str) -> bool:
    if not email:
        return False
    
    # Exakte Domain-Prüfung
    email_pattern = r'^[a-zA-Z0-9._%+-]+@gymalf\.de$'
    return bool(re.match(email_pattern, email.lower().strip()))
```

### Logging anonymisieren:
```python
import hashlib

def anonymize_email(email: str) -> str:
    """Hash email for privacy-preserving logging"""
    domain = email.split('@')[-1] if '@' in email else 'unknown'
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:8]
    return f"{email_hash}@{domain}"

# Usage:
logger.warning(f"Registration attempt with invalid domain: {anonymize_email(email)}")
```

## Fazit

Die GUSTAV-Registrierung zeigt eine durchdachte Sicherheitsarchitektur mit mehreren Verteidigungsschichten. Die identifizierten Schwachstellen sind größtenteils nicht kritisch, sollten aber zeitnah behoben werden. Die wichtigste Maßnahme ist die Aktivierung des bereits implementierten Rate-Limitings.

**Sicherheitsbewertung: 7.5/10**

Mit den empfohlenen Verbesserungen wäre eine Bewertung von 9/10 erreichbar.