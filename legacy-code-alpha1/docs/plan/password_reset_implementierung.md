# Password Reset Implementierung

## 2025-09-02T10:00:00+02:00 - OTP-basierter Password Reset Plan

### Zusammenfassung

Nach gescheiterter URL-Fragment-basierter Implementierung (siehe Historie unten) wird nun ein **OTP-basierter Ansatz** verfolgt, der 100% Streamlit-kompatibel ist.

### Implementierungsplan: OTP-basiertes Password Reset System

#### Phase 1: Database Schema (30 min)

**Neue Tabelle: `password_reset_tokens`**
```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    token VARCHAR(6) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    attempts INTEGER DEFAULT 0,
    UNIQUE(user_id, token)
);

-- RLS Policies (nur Backend-Zugriff via Service Role)
CREATE POLICY "Backend only access" ON password_reset_tokens
    FOR ALL USING (false);

-- Indexes für Performance
CREATE INDEX idx_password_reset_user_created ON password_reset_tokens(user_id, created_at);
CREATE INDEX idx_password_reset_expires ON password_reset_tokens(expires_at);

-- Automatisches Cleanup (optional)
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM password_reset_tokens WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
```

#### Phase 2: Backend Implementation (2 Stunden)

**1. Neues Modul: `app/utils/otp_service.py`**
```python
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Constants
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 15
MAX_ATTEMPTS = 3
MAX_REQUESTS_PER_HOUR = 3

def generate_otp() -> str:
    """Generiert sicheren 6-stelligen Code"""
    return ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))

def store_otp(user_id: str, db_client) -> Dict[str, Any]:
    """Speichert OTP in Datenbank mit Expiry"""
    # Rate limiting check
    # Generate OTP
    # Store in DB
    # Return result

def verify_otp(email: str, otp: str, db_client) -> Dict[str, Any]:
    """Verifiziert OTP und markiert als benutzt"""
    # Lookup OTP
    # Check expiry
    # Check attempts
    # Mark as used
    # Return user_id if valid

def cleanup_expired_otps(db_client) -> None:
    """Entfernt abgelaufene Tokens"""
```

**2. Erweiterte Funktionen in `app/auth.py`**
```python
def request_otp_password_reset(
    email: str, 
    db_client,
    email_service
) -> Dict[str, Any]:
    """
    Neuer OTP-basierter Reset Request
    - Validiert @gymalf.de Email
    - Prüft Rate Limiting (3/Stunde)
    - Generiert und speichert OTP
    - Versendet Email
    """
    
def verify_otp_and_reset_password(
    email: str,
    otp: str,
    new_password: str,
    auth_client,
    db_client
) -> Dict[str, Any]:
    """
    Verifiziert OTP und setzt neues Passwort
    - OTP-Verifikation
    - Passwort-Validierung (min. 6 Zeichen)
    - Passwort-Update via Supabase Admin API
    - OTP als benutzt markieren
    """
```

**3. Email Service: `app/utils/email_service.py`**
```python
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def send_otp_email(
    email: str, 
    otp: str,
    auth_client
) -> Dict[str, Any]:
    """
    Versendet OTP per Email via Supabase
    
    Nutzt Custom Email Template oder Supabase Invite System
    als Workaround für Email-Versand
    """
    try:
        # Option 1: Supabase Admin API für custom emails
        # Option 2: Missbrauche invite system mit OTP im metadata
        # Option 3: Externe Email API (SendGrid, etc.)
        pass
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        return {"success": False, "error": "Email-Versand fehlgeschlagen"}
```

#### Phase 3: Frontend UI Implementation (1 Stunde)

**1. Login-Seite Erweiterung (`app/main.py`)**
```python
# Nach Login-Form
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🔑 Passwort vergessen?", type="secondary", use_container_width=True):
        st.session_state.show_password_reset = True
```

**2. OTP Request Modal**
```python
def show_otp_request_modal():
    """Email-Eingabe für OTP-Anforderung"""
    with st.form("otp_request_form"):
        st.subheader("🔐 Passwort zurücksetzen")
        
        email = st.text_input(
            "Email-Adresse",
            placeholder="vorname.nachname@gymalf.de"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Code senden", type="primary")
        with col2:
            cancel = st.form_submit_button("Abbrechen")
            
        if submit:
            # Validate email
            # Call request_otp_password_reset
            # Show success/error
            # Transition to OTP input
```

**3. OTP Verification Form**
```python
def show_otp_verification_form():
    """OTP-Eingabe und neues Passwort"""
    with st.form("otp_verify_form"):
        st.subheader("🔢 Code eingeben")
        st.info(f"Code wurde an {st.session_state.otp_email} gesendet")
        
        # OTP Input (6 einzelne Felder oder ein Feld)
        otp = st.text_input(
            "6-stelliger Code",
            max_chars=6,
            placeholder="123456"
        )
        
        # Neues Passwort
        new_password = st.text_input("Neues Passwort", type="password")
        confirm_password = st.text_input("Passwort bestätigen", type="password")
        
        # Attempts counter
        if hasattr(st.session_state, 'otp_attempts'):
            st.caption(f"Versuche: {st.session_state.otp_attempts}/3")
        
        submit = st.form_submit_button("Passwort ändern", type="primary")
        
        if submit:
            # Validate inputs
            # Call verify_otp_and_reset_password
            # Handle success/error
            # Auto-login on success
```

#### Phase 4: Email Template (30 min)

**OTP Email Template (HTML)**
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        .otp-container {
            text-align: center;
            padding: 40px;
            font-family: Arial, sans-serif;
        }
        .otp-code {
            font-size: 36px;
            font-weight: bold;
            letter-spacing: 8px;
            color: #2563eb;
            background: #f3f4f6;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .warning {
            color: #dc2626;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="otp-container">
        <h2>Passwort zurücksetzen</h2>
        <p>Ihr Code für die Passwort-Zurücksetzung:</p>
        <div class="otp-code">{{ otp }}</div>
        <p class="warning">⏱️ Gültig für 15 Minuten</p>
        <p>Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese Email.</p>
        <hr>
        <p><small>GUSTAV - Vertretungslehrer System</small></p>
    </div>
</body>
</html>
```

#### Phase 5: Testing & Security (1 Stunde)

**Test Cases (`app/tests/test_otp_password_reset.py`)**
```python
def test_otp_generation():
    """OTP ist 6 Zeichen, nur Zahlen"""
    
def test_otp_storage():
    """OTP wird korrekt gespeichert mit Expiry"""
    
def test_rate_limiting():
    """Max 3 Requests pro Stunde"""
    
def test_otp_verification_success():
    """Gültiger OTP funktioniert"""
    
def test_otp_expiry():
    """Abgelaufener OTP wird abgelehnt"""
    
def test_max_attempts():
    """Nach 3 Versuchen gesperrt"""
    
def test_concurrent_requests():
    """Mehrere OTPs gleichzeitig"""
```

**Security Checklist:**
- ✅ Cryptographically secure OTP generation (secrets module)
- ✅ Time-based expiry (15 Minuten)
- ✅ Rate limiting (3 Anfragen/Stunde)
- ✅ Max attempts (3 Versuche pro OTP)
- ✅ No OTP in logs
- ✅ Timing attack prevention
- ✅ SQL injection prevention (parameterized queries)

#### Phase 6: Documentation Update (30 min)

1. Update `CHANGELOG.md`
2. User Guide in `docs/user/password-reset.md`
3. Update `ARCHITECTURE.md` Authentication section
4. Update dieser Implementierungsdatei

### Vorteile der OTP-Lösung

1. **100% Streamlit-kompatibel** - Keine URL-Fragment-Probleme
2. **Bessere UX** - Nutzer bleibt in der App
3. **Mobile-friendly** - Einfache Eingabe von 6 Ziffern
4. **Sicherer** - Kein Link-Hijacking möglich
5. **Debuggable** - Jeder Schritt nachvollziehbar
6. **Offline-tauglich** - OTP kann abgeschrieben werden

### Migrations-Strategie

1. **Schritt 1:** Admin-Info auf Login-Seite (sofort)
2. **Schritt 2:** OTP-System implementieren (1 Tag)
3. **Schritt 3:** Beta-Test mit ausgewählten Nutzern
4. **Schritt 4:** Vollständiger Rollout
5. **Fallback:** Admin-Reset bleibt verfügbar

### Offene Entscheidungen

1. **Email-Versand-Methode:**
   - Option A: Supabase Auth API (invite system hack)
   - Option B: Eigener SMTP-Server
   - Option C: SendGrid/Postmark Integration

2. **OTP-Format:**
   - Option A: 6 Ziffern (Standard)
   - Option B: 4 Ziffern (einfacher)
   - Option C: Alphanumerisch (sicherer)

3. **Storage Backend:**
   - Option A: PostgreSQL (empfohlen)
   - Option B: Redis (wenn verfügbar)
   - Option C: In-Memory (nur Development)

---

## 2025-01-02T14:30:00+01:00

**Ziel:** Vollständige Password-Reset-Funktionalität mit UI-Integration implementieren

**Annahmen:**
- Supabase Email-Konfiguration funktioniert bereits (bestätigt durch existierende recovery.html)
- Recovery-Token-Handling in main.py ist Basis für Integration
- @gymalf.de Email-Beschränkung bleibt bestehen
- Bestehende Auth-Patterns werden befolgt

**Offene Punkte:**
- ✅ E-Mail-Beschränkung: Nur @gymalf.de Adressen (wie bei Registrierung)
- ✅ Rate-Limiting: Pro Nutzer 2 Requests pro Stunde (zusätzlich zu Supabase-Limits)
- ✅ Success-Page: Zurück zum Login mit Success-Message (Option C)

**Beschluss:** Vollständige UI-Integration (Option 1) mit folgenden Komponenten

**Status:** ✅ VOLLSTÄNDIG IMPLEMENTIERT

---

## 2025-01-02T15:45:00+01:00 - Implementierung abgeschlossen

**Implementierte Komponenten:**

### Backend (app/auth.py)
- ✅ `request_password_reset(email)` - Email-Validierung (@gymalf.de), Rate-Limiting (2/Stunde), Supabase-Integration
- ✅ `update_password(new_password)` - Passwort-Validierung (min. 6 Zeichen), Recovery-Token-Nutzung
- ✅ `_is_gymalf_email()` und `_check_password_reset_rate_limit()` - Hilfsfunktionen
- ✅ Type Hints und Google-Style Docstrings für alle Funktionen

### Frontend (app/main.py)  
- ✅ "🔑 Passwort vergessen?" Button im Login-Form
- ✅ `show_password_reset_modal()` - Email-Eingabe-Modal mit Validierung
- ✅ `show_password_update_form()` - Neues-Passwort-Form für Recovery-Links
- ✅ Recovery-Token-Erkennung über Query-Parameter `?type=recovery`
- ✅ Success-Message nach erfolgreichem Reset
- ✅ Session-State-Management für UI-Flow

### Tests (app/tests/test_password_reset.py)
- ✅ Unit Tests für Email-Validierung (`_is_gymalf_email`)
- ✅ Rate-Limiting-Tests (Happy Path, Rate-Limit erreicht, Cleanup alter Requests)
- ✅ Integration Tests für `request_password_reset()` (Success, Fehler-Cases)
- ✅ Tests für `update_password()` (Success, Validierung, Supabase-Fehler)
- ✅ Mocking für Supabase-Client und Session-State

**Implementierungsdetails:**
- Rate-Limiting: 2 Requests/Stunde pro Email (in Session-State gespeichert)
- Email-Beschränkung: Nur @gymalf.de Adressen erlaubt
- Passwort-Anforderungen: Mindestens 6 Zeichen
- Recovery-URL: `SITE_URL?type=recovery` (aus Streamlit Secrets)
- Error-Handling: Nutzerfreundliche Meldungen, Logging für Debug

**Security-Features:**
- Email-Domain-Validierung
- Rate-Limiting auf Client-Seite
- Passwort-Längen-Validierung  
- Sichere Session-Token-Nutzung
- Keine PII in Logs

**Nächste Schritte:** Refactoring für bessere Testbarkeit (siehe Option B unten)

---

## 2025-01-02T16:15:00+01:00 - Verbesserungsvorschlag: Dependency Injection (Option B)

**Problem der aktuellen Implementierung:**
- Tight Coupling zu Streamlit Session State macht Unit Tests unmöglich
- Business Logic direkt mit UI-Framework gekoppelt
- Rate-Limiting in flüchtigem Browser-State (nicht persistent)
- Funktionen sind isoliert nicht testbar

**Lösungsansatz: Dependency Injection**

### Refactoring-Plan

#### 1. Session-Dependencies als Parameter
**Vorher:**
```python
def _check_password_reset_rate_limit(email: str) -> bool:
    if "password_reset_requests" not in st.session_state:  # ❌ Globale Abhängigkeit
```

**Nachher:**
```python
def _check_password_reset_rate_limit(email: str, session_store: dict) -> bool:
    if "password_reset_requests" not in session_store:  # ✅ Parameter
```

#### 2. Client-Dependencies injizieren
**Vorher:**
```python
def request_password_reset(email: str) -> Dict[str, Any]:
    client = get_anon_supabase_client()  # ❌ Hard dependency
```

**Nachher:**
```python
def request_password_reset(email: str, auth_client, session_store: dict) -> Dict[str, Any]:
    # ✅ Beide Dependencies als Parameter
```

#### 3. Streamlit-Layer als Adapter
```python
# In main.py - UI ruft Business Logic mit konkreten Dependencies auf
def show_password_reset_modal():
    # ... UI Code ...
    if submit_reset:
        result = request_password_reset(
            email=reset_email,
            auth_client=get_anon_supabase_client(),
            session_store=st.session_state
        )
```

### Vorteile dieser Änderung

**Testbarkeit:**
- Business Logic isoliert testbar (keine Streamlit-Dependencies)
- Mock-Objects als Parameter übergeben
- Unit Tests laufen ohne Streamlit-App-Kontext

**Flexibilität:**
- Session-Storage austauschbar (Redis, Database, Memory)
- Auth-Client mockbar für Tests
- Verschiedene Storage-Backends möglich

**Wartbarkeit:**
- Klare Trennung UI vs. Business Logic
- Dependencies explizit sichtbar
- Einfachere Code-Reviews

### Implementierungsaufwand

**Minimal:** Nur Funktions-Signaturen ändern
- `auth.py`: 2 Funktionen erweitern (+2 Parameter jeweils)
- `main.py`: 2 Aufrufe anpassen (Parameter hinzufügen)
- `test_*.py`: Tests funktionieren dann ohne Mocking-Probleme

**Geschätzter Aufwand:** 30-60 Minuten
**Risk:** Niedrig - Rückwärtskompatibel durch Parameter-Default-Werte möglich

### Langfristige Optionen
- **Option C:** Database Rate-Limiting für echte Persistence
- **Option D:** Repository Pattern für DB-Abstraktion  
- **Option A:** Clean Architecture für maximale Sauberkeit

**Empfehlung:** Option B als Sofortmaßnahme, dann schrittweise C+D

---

## 2025-01-02T17:30:00+01:00 - Option B umgesetzt + Code-Qualitäts-Analyse

### ✅ Dependency Injection erfolgreich implementiert

**Umgesetzte Verbesserungen:**
- ✅ `_check_password_reset_rate_limit(email, session_store)` - Session als Parameter
- ✅ `_add_password_reset_request(email, session_store)` - Session als Parameter  
- ✅ `request_password_reset(email, auth_client, session_store, site_url)` - Dependencies injiziert
- ✅ `update_password(new_password, auth_client)` - Client als Parameter
- ✅ `main.py` - Aufrufe angepasst, Dependencies explizit übergeben
- ✅ Tests korrigiert - keine Streamlit-Dependencies mehr

**Tests bestätigt:** Core-Funktionen arbeiten korrekt mit Dependency Injection

### 📊 Code-Qualitätsbewertung: 6/10

**Erreichte Verbesserungen:**
- Business Logic von UI entkoppelt ✅
- Testbare Funktionen ✅  
- Explizite Dependencies ✅
- Gute Dokumentation ✅

### 🔧 Identifizierte Verbesserungsmöglichkeiten

#### Priorität 1: Kleinere Verbesserungen (< 30 Min)

**1. Fehlende Type Hints (5 Min)**
```python
# Aktuell
def request_password_reset(email: str, auth_client, session_store: Dict[str, Any])
#                                    ↑ Missing type hint

# Soll  
def request_password_reset(email: str, auth_client: SupabaseClient, session_store: Dict[str, Any])
```

**2. Magic Strings eliminieren (10 Min)**
```python
# Aktuell
"password_reset_requests"  # Mehrfach verwendet
{"success": False, "error": "..."}  # Wiederholende Struktur

# Soll
PASSWORD_RESET_REQUESTS_KEY = "password_reset_requests"
class ResetResult(TypedDict):
    success: bool
    error: Optional[str]
```

**3. Magic Numbers in Constants (5 Min)**
```python
# Aktuell
if len(recent_requests) >= 2:  # Magic number
if len(new_password) < 6:     # Magic number

# Soll
MAX_RESET_REQUESTS_PER_HOUR = 2
MIN_PASSWORD_LENGTH = 6
```

**4. UI-Integration verbessern (10 Min)**
```python
# ❌ PROBLEM: "Passwort vergessen?" Button nicht schön integriert
# Aktuell: Button in Form mit Trennlinie - wirkt zusammenhangslos
st.markdown("---")  # Harte Trennung
if st.form_submit_button("🔑 Passwort vergessen?", type="secondary"):

# ✅ LÖSUNG: Dezenter Link außerhalb der Form
# Nach Login-Form, als small/caption-Link unter dem Button
```

#### Priorität 2: Strukturelle Verbesserungen (30-60 Min)

**5. Single Responsibility für UI-Funktionen**
```python
# Aktuell: show_password_reset_modal() macht zu viel
# - UI rendern + Business Logic + State Management + Sleep/Rerun

# Soll: Aufteilen in:
# - render_password_reset_form() -> UI only  
# - handle_password_reset_submit() -> Logic only
# - manage_reset_state() -> State only
```

**6. Error-Types typisieren**
```python
# Aktuell: Verschiedene Error-Strings
"Nur @gymalf.de Email-Adressen sind erlaubt."
"Zu viele Anfragen. Bitte warten Sie eine Stunde."

# Soll: Enum/Constants
class ResetError(Enum):
    INVALID_EMAIL_DOMAIN = "invalid_email_domain"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    NETWORK_ERROR = "network_error"
```

#### Priorität 3: Langfristige Architektur-Verbesserungen

**7. Database Rate-Limiting (Option C)**
- Session-basiertes Rate-Limiting ist umgehbar durch neuen Browser
- Persistent Rate-Limiting in DB-Tabelle

**8. Repository Pattern (Option D)**  
- Auth-Repository für saubere DB-Abstraktion
- Bessere Testbarkeit und Austauschbarkeit

**9. Result-Types statt Dict**
```python
# Aktuell
def request_password_reset(...) -> Dict[str, Any]:
    return {"success": False, "error": "..."}

# Soll
def request_password_reset(...) -> Result[None, ResetError]:
    return Err(ResetError.INVALID_EMAIL_DOMAIN)
```

### 🎯 Empfohlene nächste Schritte

1. **Sofort (< 30 Min):** Priorität 1 abarbeiten - Type Hints, Constants, UI-Integration
2. **Kurzfristig (1-2h):** Priorität 2 - UI-Funktionen aufteilen, Error-Types
3. **Mittelfristig:** Database Rate-Limiting implementieren
4. **Langfristig:** Repository Pattern + Result-Types für maximale Code-Qualität

---

## 2025-09-02T08:15:00+01:00 - Implementierung FEHLGESCHLAGEN: Architektur-Inkompatibilität

### ❌ **STATUS: NICHT FUNKTIONSFÄHIG**

**Problem-Zusammenfassung:** Automatischer Password-Reset-Flow über Email-Links kann in Streamlit-Architektur nicht implementiert werden.

### 🔍 **Root-Cause-Analyse**

#### **Problem #1: Supabase Dashboard Override**
```
// Code-Einstellung (ignoriert):
redirect_to = "https://domain.com/reset/password-reset-bridge.html"

// Tatsächlicher Email-Link:
redirect_to = "https://domain.com"

// Ursache: Supabase Dashboard "Site URL" überschreibt programmatischen redirect_to
```
**Status:** 🚫 **BLOCKIERT** - Keine Dashboard-Kontrolle verfügbar

#### **Problem #2: HTTP-Protokoll Limitation**
```
Browser Request: GET /app?param=value#fragment
Server erhält:   GET /app?param=value
                 ↑ Fragment wird nie übertragen (HTTP-Standard)
```
**Supabase sendet Token als URL-Fragmente:** `#access_token=...&refresh_token=...&type=recovery`  
**Streamlit kann nur Query-Parameter lesen:** `?access_token=...`

**Status:** 🚫 **PROTOKOLL-LIMITATION** - Fundamental unmöglich in Server-Side-Rendering

#### **Problem #3: JavaScript Execution Timing**
```
1. Python läuft durch → Entscheidet über UI-State (show_login=True)
2. HTML/JavaScript wird an Browser gesendet
3. JavaScript läuft asynchron → Aber Python ist bereits fertig
4. URL-Redirect durch JS → Neue Python-Ausführung, Token-Info bereits verloren
```
**Status:** 🚫 **ARCHITEKTUR-INKOMPATIBILITÄT** - Client-side JS vs. Server-side Python

### 🛠️ **Getestete Lösungsansätze (alle fehlgeschlagen)**

#### **Ansatz 1: JavaScript Fragment-Konverter**
```javascript
// In main.py
st.components.v1.html("""
<script>
if (window.location.hash.includes('access_token')) {
    window.location.replace(baseUrl + '?' + hash);  
}
</script>
""", height=0)
```
**Ergebnis:** ❌ Race Condition - Python bereits fertig wenn JavaScript läuft

#### **Ansatz 2: HTML-Zwischenseite mit nginx**
```nginx
# nginx.conf
location /reset/ {
    alias /var/www/static/;
}
```
```python
# auth.py  
redirect_url = site_url + "/reset/password-reset-bridge.html"
```
**Ergebnis:** ❌ Supabase Dashboard überschreibt weiterhin redirect_to Parameter

#### **Ansatz 3: Environment Variable Override**
```bash
# .env
SITE_URL="https://domain.com/reset/password-reset-bridge.html"
```
**Ergebnis:** ❌ Dashboard-Override bleibt bestehen, Email-Link unverändert

#### **Ansatz 4: Manuelle Recovery-Session**
```python
# Versuch: Session aus URL-Parametern erstellen
access_token = st.query_params.get("access_token")  # Immer None!
recovery_client.auth._session = create_session(access_token)
```
**Ergebnis:** ❌ Basis-Annahme falsch - Token sind nie in Query-Parametern

### 🧹 **Bereinigung durchgeführt**

**Entfernte Komponenten:**
- ❌ HTML-Bridge-Datei gelöscht: `/static/password-reset-bridge.html`
- ❌ nginx Location-Block entfernt: `location /reset/`
- ❌ Docker Volume-Mapping entfernt: `./static:/var/www/static:ro`
- ❌ auth.py redirect_url zurückgesetzt auf Standard
- ❌ main.py Recovery-Session-Code entfernt
- ❌ SITE_URL aus .env entfernt
- ❌ "Passwort vergessen?"-Button aus UI entfernt

**Verbleibend (für zukünftige Implementierung):**
- ✅ Backend-Funktionen (`request_password_reset`, `update_password`) 
- ✅ Tests (`test_password_reset.py`)
- ✅ Constants und Type Hints (Priorität 1 Verbesserungen)

### 💡 **Funktionierende Alternativen**

#### **Option A: nginx Redirect Rule** ⭐ **EMPFOHLEN**
```nginx
location ~ ^/auth/v1/verify.*type=recovery {
    return 302 /reset-bridge.html$is_args$args;
}
```
- **Vorteile:** Umgeht Supabase Dashboard, funktioniert server-seitig
- **Aufwand:** 30 Minuten
- **Erfolgswahrscheinlichkeit:** 95%

#### **Option B: OTP-basierte Lösung** ⭐ **LANGFRISTIG OPTIMAL**
```python
1. Generiere 6-stelligen Code
2. Speichere in DB mit 15min Expiry  
3. Sende per Email (kein Link!)
4. User gibt Code in Streamlit-Form ein
```
- **Vorteile:** 100% Streamlit-kompatibel, keine URL-Fragmente, bessere UX
- **Aufwand:** 3-4 Stunden
- **Erfolgswahrscheinlichkeit:** 100%

#### **Option C: Admin-gestützte Lösung** ⚡ **SOFORT VERFÜGBAR**
```python
st.info("📧 Bei Reset-Problemen admin@gymalf.de kontaktieren")
# Admin setzt Passwort über Supabase Dashboard
```
- **Vorteile:** Funktioniert sofort, kein Code
- **Aufwand:** 1 Minute
- **Erfolgswahrscheinlichkeit:** 100%

### 📊 **Lessons Learned**

1. **Architektur-Mismatch:** Client-first (Supabase) vs. Server-first (Streamlit) Design
2. **Dashboard dominiert Code:** SaaS-Plattformen überschreiben oft programmatische Einstellungen  
3. **HTTP-Fragmente ungeeignet für SSR:** Server-side Rendering kann client-side Daten nicht verarbeiten
4. **JavaScript-Timing in Streamlit problematisch:** Asynchrone Execution macht Fragment-Processing unmöglich
5. **Email-Links sind nicht "unsere" URLs:** Externe Services bestimmen URL-Struktur

### 🎯 **Empfohlene Vorgehensweise**

**Phase 1 (Sofort):** Option C implementieren - Admin-gestützte Lösung für Produktionsbetrieb  
**Phase 2 (1-2 Wochen):** Option A testen - nginx Redirect Rule als technische Lösung  
**Phase 3 (Mittelfristig):** Option B implementieren - OTP-System für optimale User Experience  
**Phase 4 (Langfristig):** UI-Migration zu client-seitiger Architektur (Next.js/React) für vollständige Supabase-Kompatibilität

---

**Fazit:** Password-Reset-Funktionalität ist in reiner Streamlit-Architektur nicht vollständig implementierbar. Backend-Code bleibt für zukünftige Implementierung erhalten, UI-Integration erfordert alternative Ansätze.

---

## Implementierungsplan

### Phase 1: Backend-Funktionen (auth.py)
1. **request_password_reset(email: str)**
   - Validierung der Email-Adresse (@gymalf.de Required)
   - Rate-Limiting: 2 Requests pro Nutzer/Stunde
   - Aufruf von supabase.auth.reset_password_email()
   - Error-Handling für nicht existierende User
   - Logging für Security-Monitoring

2. **update_password(new_password: str)**
   - Nutzt authenticated Session aus Recovery-Token
   - Validierung der Passwort-Stärke (min. 6 Zeichen)
   - Aufruf von supabase.auth.update_user()
   - Session-Invalidierung nach erfolgreichem Update

### Phase 2: UI-Komponenten (main.py)
1. **Login-Form-Erweiterung**
   - "Passwort vergessen?" Link unter Login-Button
   - Styling passend zum bestehenden Design
   - State-Management für UI-Flow

2. **Password-Reset-Request-Modal**
   - Email-Eingabefeld mit Validierung
   - Success/Error-Messages
   - "Zurück zum Login" Option
   - Loading-State während Email-Versand

3. **New-Password-Form (Recovery-Flow)**
   - Erkennung des type=recovery Query-Parameters
   - Passwort-Eingabe mit Bestätigung
   - Passwort-Stärke-Indikator (optional)
   - Nach erfolgreichem Reset: Zurück zu Login mit Success-Message

### Phase 3: Session & State Management
1. **Session-States**
   - `password_reset_requested`: Nach Email-Versand
   - `password_reset_in_progress`: Während Token-Verarbeitung
   - `password_reset_complete`: Nach erfolgreichem Reset

2. **Error-States**
   - Invalid/Expired Token
   - Network Errors
   - Validation Errors

### Phase 4: Testing & Security
1. **Unit Tests**
   - auth.py Funktionen
   - Email-Validierung
   - Password-Validierung

2. **Integration Tests**
   - Complete Reset Flow
   - Token-Expiry-Handling
   - Session-Management

3. **Security-Checks**
   - Rate-Limiting-Verhalten
   - Token-Sicherheit
   - Session-Isolation

### Phase 5: Dokumentation
1. **User-Dokumentation**
   - Anleitung für Password-Reset
   - FAQ für häufige Probleme

2. **Code-Dokumentation**
   - Inline-Comments für komplexe Logik
   - Update der ARCHITECTURE.md

## Technische Details

### Supabase Auth API Calls
```python
# Password Reset Request
supabase.auth.reset_password_email(
    email=email,
    redirect_to=f"{BASE_URL}?type=recovery"
)

# Password Update (mit Recovery Token)
supabase.auth.update_user({
    "password": new_password
})
```

### UI-Flow-Diagramm
```
Login-Page → [Passwort vergessen?] → Email-Modal → Success-Message
                                          ↓
                                    Email gesendet
                                          ↓
User klickt Link → main.py?type=recovery → New-Password-Form → Auto-Login
```

### Risiken & Mitigationen
1. **Email-Delivery-Probleme**
   - Mitigation: Clear User-Feedback, Support-Kontakt anbieten

2. **Token-Expiry während Eingabe**
   - Mitigation: Clear Error-Message, Neuen Reset-Link anfordern

3. **Brute-Force-Attacken**
   - Mitigation: Supabase Rate-Limiting, Monitoring

### Rollback-Plan
- Feature-Flag für Password-Reset-UI
- Fallback auf Supabase-Dashboard-Methode
- Alle Änderungen sind isoliert und rückgängig machbar