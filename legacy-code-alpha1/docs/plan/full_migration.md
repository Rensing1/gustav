# Full Migration Plan: Streamlit → FastAPI + HTMX

**Erstellt:** 2025-01-11  
**Status:** In Planung  
**Ziel:** Komplette Neuimplementierung der Gustav-Plattform mit modernem, minimalistischem Tech-Stack

## Wichtige Anforderungen

- **Flexible Authentifizierung:** Die Plattform muss sowohl mit als auch ohne IServ funktionieren
- **Manuelle Gruppenverwaltung:** Admins können Nutzer manuell Gruppen/Kursen zuordnen
- **IServ als Option:** SSO-Integration ist ein zusätzliches Feature, kein Zwang
- **Standard-Login immer verfügbar:** Email/Password-basierte Anmeldung als Basis

## Executive Summary

Nach ausführlicher Analyse empfehlen wir die Migration von Streamlit zu **FastAPI + HTMX + Tailwind CSS**. Diese Lösung bietet maximale Einfachheit, Performance und Sicherheit bei minimalem Code und ohne Build-Prozess.

## Evaluierte Optionen

### Option 1: Django + HTMX (Verworfen)
**Überlegung:** Django als "Batteries-included" Framework mit HTMX für partielle Updates

**Vorteile:**
- Django Admin Interface
- Integriertes ORM und Migrations-System
- Django Forms für automatische Validierung
- Große Community und Ecosystem

**Nachteile:**
- Mehr Boilerplate und Struktur-Overhead
- Django-spezifische Patterns (MVT) zu lernen
- Schwergewichtiger als nötig für unsere Anforderungen
- Zusätzliche Abstraktion über der Datenbank

**Entscheidung:** Verworfen zugunsten eines minimalistischeren Ansatzes

### Option 2: Reine Web Components (Verworfen)
**Überlegung:** Vanilla Web Components oder Lit für maximale Standards-Konformität

**Vorteile:**
- Keine Framework-Abhängigkeiten
- Zukunftssicher durch Web Standards
- Volle Kontrolle über Komponenten

**Nachteile:**
- Mehr JavaScript-Code nötig
- Shadow DOM Komplexität
- Build-Step für optimale Performance
- Zwei Sprachen (Python + JavaScript)

**Entscheidung:** Verworfen, da zu viel Client-side Komplexität

### Option 3: FastAPI + HTMX + Tailwind (Gewählt) ✅
**Überlegung:** Minimalistischer Stack mit Server-side Rendering

**Vorteile:**
- Kein Build-Prozess nötig
- Eine Sprache (99% Python)
- CDN für CSS/JS Dependencies
- Native Cookie/Session Support
- Perfekte Integration mit bestehenden Services
- Extrem schnelle Ladezeiten
- SEO-freundlich

**Nachteile:**
- Weniger "magische" Features als Django
- Forms müssen manuell gebaut werden

**Entscheidung:** Gewählt als optimaler Kompromiss zwischen Einfachheit und Funktionalität

## Technische Architektur

### Frontend Stack
```
- HTML: Jinja2 Templates (Server-side Rendering)
- Interaktivität: HTMX (Hypermedia-driven)
- Styling: Tailwind CSS (Utility-first)
- Kleine UI-Logik: Alpine.js (optional, für lokale State)
- Icons: Heroicons oder Tabler Icons (SVG)
```

### Backend Stack
```
- API: FastAPI (bereits vorhanden)
- Database: PostgreSQL/Supabase (unverändert)
- Auth: Bestehender Auth-Service + IServ SSO (optional)
- Storage: Supabase Storage (unverändert)
- Workers: Feedback Worker (unverändert)
- Cache: Redis (optional, für Sessions)
```

### Projekt-Struktur
```
gustav/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI App
│   ├── endpoints/           # Route Handler
│   │   ├── auth.py         # Login, SSO, Sessions
│   │   ├── courses.py      # Kursverwaltung
│   │   ├── tasks.py        # Aufgaben
│   │   └── ai.py           # KI-Integration
│   ├── dependencies.py      # Shared Dependencies
│   └── models.py           # Pydantic Models
├── templates/
│   ├── base.html           # Layout mit HTMX/Tailwind
│   ├── pages/              # Vollständige Seiten
│   │   ├── dashboard.html
│   │   ├── course_detail.html
│   │   └── task_submit.html
│   └── components/         # Wiederverwendbare Fragmente
│       ├── task_card.html
│       ├── user_list.html
│       └── feedback_view.html
├── static/                 # Nur eigene Assets
│   ├── favicon.ico
│   └── logo.svg
├── services/              # Bestehende Services
│   ├── auth/             # Unverändert
│   ├── feedback_worker/  # Unverändert
│   └── migrations/       # Supabase Migrations
└── docker-compose.yml    # Vereinfacht
```

## Implementation Details

### 1. Cookie-basierte Authentifizierung
```python
# Endlich HttpOnly Cookies!
response.set_cookie(
    key="auth_token",
    value=jwt_token,
    httponly=True,  # XSS-Schutz
    secure=True,    # HTTPS only
    samesite="lax", # CSRF-Schutz
    max_age=86400   # 24h
)
```

### 2. HTMX für Interaktivität
```html
<!-- Keine Full-Page Reloads mehr -->
<button hx-post="/api/task/submit" 
        hx-target="#result"
        hx-swap="innerHTML"
        hx-indicator="#spinner">
    Abgeben
</button>
```

### 3. File Uploads (Nativ!)
```html
<form hx-post="/upload" 
      hx-encoding="multipart/form-data">
    <input type="file" name="file" multiple>
</form>
```

### 4. Server-Sent Events für Realtime
```python
# KI Streaming, Live-Updates
async def stream_response():
    async for chunk in ai_service.generate():
        yield f"data: {chunk}\n\n"
```

### 5. Flexible Authentifizierung

#### Standard Login (Email/Password)
```python
@app.post("/auth/login")
async def login(credentials: LoginSchema, response: Response):
    # Validierung gegen eigene User-Datenbank
    user = await authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    # JWT Token erstellen
    token = create_jwt_token(user)
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=True
    )
    return {"redirect": "/dashboard"}

@app.post("/auth/register")
async def register(user_data: RegisterSchema):
    # Neue Nutzer können sich selbst registrieren
    user = await create_user(
        email=user_data.email,
        password=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role  # student/teacher
    )
    # Manuelle Gruppenzuordnung erfolgt später durch Admin
    return {"message": "Registration successful"}
```

#### IServ SSO Integration (Optional)
```python
# Nur wenn IServ konfiguriert ist
if settings.ISERV_ENABLED:
    @app.get("/auth/iserv/login")
    async def iserv_login(request: Request):
        return await oauth.iserv.authorize_redirect(request)

    @app.get("/auth/iserv/callback")
    async def iserv_callback(request: Request):
        token = await oauth.iserv.authorize_access_token(request)
        # Auto-Provisioning von Usern und Gruppen
        user_data = await get_iserv_user_info(token)
        user = await provision_or_update_user(user_data)
        return create_session_and_redirect(user)
```

#### Manuelle Gruppenverwaltung
```python
@app.post("/api/users/{user_id}/groups")
async def assign_user_to_group(
    user_id: int,
    group_data: GroupAssignment,
    admin_user = Depends(require_admin)
):
    # Admin kann Nutzer manuell Gruppen/Kursen zuordnen
    await db.execute(
        "INSERT INTO user_groups (user_id, group_id) VALUES ($1, $2)",
        user_id, group_data.group_id
    )
    return {"message": "User assigned to group"}
```

## Migrations-Strategie

### Phase 1: Proof of Concept (Woche 1)
- [ ] FastAPI + HTMX Setup
- [ ] Eine kritische Seite nachbauen (Dashboard)
- [ ] Auth-Flow mit Cookies testen
- [ ] Performance-Vergleich mit Streamlit

### Phase 2: Core Infrastructure (Woche 2-3)
- [ ] Template-System aufsetzen
- [ ] Auth Middleware implementieren
- [ ] Session Management
- [ ] Error Handling
- [ ] Security Headers

### Phase 3: Feature Migration (Woche 4-8)
**Priorität 1: Kritische Features**
- [ ] Login/Logout (Cookie-based)
- [ ] Dashboard (Student/Teacher Views)
- [ ] Kursübersicht
- [ ] Aufgabenabgabe

**Priorität 2: Erweiterte Features**
- [ ] File Upload System
- [ ] Wissensfestiger
- [ ] Live-Feedback Integration
- [ ] KI-Chat mit Streaming

**Priorität 3: Admin Features**
- [ ] Kursverwaltung
- [ ] Nutzerverwaltung (inkl. manueller Gruppenzuordnung)
- [ ] Statistiken
- [ ] IServ SSO Setup (optional)

### Phase 4: Testing & Optimierung (Woche 9-10)
- [ ] End-to-End Tests
- [ ] Performance Optimierung
- [ ] Browser-Kompatibilität
- [ ] Mobile Responsiveness

### Phase 5: Migration & Rollout (Woche 11-12)
- [ ] Daten-Migration Skripte
- [ ] A/B Testing Setup
- [ ] Schrittweise User-Migration
- [ ] Monitoring einrichten
- [ ] Streamlit abschalten

## Vorteile gegenüber Streamlit

| Aspekt | Streamlit | FastAPI + HTMX |
|--------|-----------|-----------------|
| **Cookies** | ❌ Keine HttpOnly | ✅ Native Unterstützung |
| **File Upload** | ❌ Workarounds nötig | ✅ Standard HTML |
| **Performance** | ❌ Full Reloads | ✅ Partielle Updates |
| **SEO** | ❌ Client-side | ✅ Server-side |
| **Sessions** | ❌ Session Bleeding | ✅ Isolierte Sessions |
| **Customization** | ❌ Begrenzt | ✅ Volle Kontrolle |
| **Bundle Size** | ❌ ~3MB | ✅ ~50KB |

## Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|---------|------------|
| HTMX Learning Curve | Niedrig | Niedrig | Dokumentation, Beispiele |
| Feature-Parität | Mittel | Hoch | Feature-Freeze, klare Priorisierung |
| Daten-Migration | Niedrig | Hoch | Ausführliche Tests, Rollback-Plan |
| Performance-Regression | Niedrig | Mittel | Profiling, Caching-Strategie |

## Security Considerations

### Überblick: Sicherheit als Fundament

Bei der Migration von Streamlit zu FastAPI+HTMX müssen wir einige Sicherheitsaspekte selbst implementieren, die bei anderen Frameworks automatisch dabei sind. Das ist aber kein Grund zur Sorge - mit 8-12 Stunden einmaligem Aufwand haben wir eine robuste Security-Architektur.

### Die wichtigsten Bedrohungen und unsere Gegenmaßnahmen

#### 1. Cross-Site Scripting (XSS) - "Der Code-Einschleuser"
**Was ist das?** Ein Angreifer versucht, JavaScript-Code in unsere Seiten einzuschleusen.

**Beispiel-Angriff:**
```javascript
// Böser User gibt als Namen ein:
<script>alert('Gehackt!')</script>
```

**Unsere Verteidigung:**
```python
# Automatisches HTML-Escaping in Jinja2
templates = Jinja2Templates(directory="templates", autoescape=True)

# In Templates wird alles automatisch escaped:
# {{ user.name }} wird zu &lt;script&gt;alert('Gehackt!')&lt;/script&gt;

# Für vertrauenswürdigen Content (z.B. KI-Feedback):
from markupsafe import Markup
safe_content = Markup(ai_feedback)  # Explizit als sicher markieren
```

#### 2. Cross-Site Request Forgery (CSRF) - "Der Identitätsdieb"
**Was ist das?** Eine böse Website versucht, im Namen des eingeloggten Users Aktionen auszuführen.

**Beispiel-Angriff:**
```html
<!-- Auf evil.com -->
<img src="https://gustav.de/api/delete-all-courses" />
```

**Unsere Verteidigung:**
```python
# CSRF-Token Setup (einmalig)
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel

class CsrfSettings(BaseModel):
    secret_key: str = "your-32-char-secret"

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

# In HTML-Template
<meta name="csrf-token" content="{{ csrf_token }}">
<script>
// HTMX sendet Token automatisch mit
document.body.addEventListener('htmx:configRequest', (e) => {
    e.detail.headers['X-CSRFToken'] = 
        document.querySelector('meta[name="csrf-token"]').content;
});
</script>
```

#### 3. SQL Injection - "Der Datenbank-Manipulator"
**Was ist das?** Angreifer versucht, SQL-Befehle in Input-Felder einzuschleusen.

**Beispiel-Angriff:**
```sql
-- User gibt als Task-ID ein:
1; DROP TABLE users; --
```

**Unsere Verteidigung:**
```python
# NIEMALS String-Concatenation!
# ❌ GEFÄHRLICH:
query = f"SELECT * FROM tasks WHERE id = {task_id}"

# ✅ SICHER - Parametrisierte Queries:
result = await db.fetch_one(
    "SELECT * FROM tasks WHERE id = $1 AND user_id = $2",
    task_id,  # Wird automatisch escaped
    user_id   # Wird automatisch escaped
)

# Zusätzlich: Input-Validierung mit Pydantic
from pydantic import BaseModel, validator

class TaskSubmission(BaseModel):
    task_id: int  # Muss eine Zahl sein!
    text: str
    
    @validator('text')
    def validate_text(cls, v):
        if len(v) > 10000:
            raise ValueError('Text zu lang')
        return v
```

#### 4. Session Hijacking - "Der Cookie-Dieb"
**Was ist das?** Angreifer versucht, die Session-Cookies zu stehlen.

**Unsere Verteidigung:**
```python
# Sichere Cookie-Einstellungen
response.set_cookie(
    key="session_id",
    value=encrypted_session_id,
    httponly=True,     # JavaScript kann nicht zugreifen
    secure=True,       # Nur über HTTPS
    samesite="strict", # Keine Cross-Site Requests
    max_age=3600,      # Läuft nach 1 Stunde ab
)

# Session-Rotation nach Login
@app.post("/auth/login")
async def login(credentials: LoginSchema, request: Request):
    # Alte Session ungültig machen
    request.session.clear()
    
    # Neue Session-ID generieren
    request.session["user_id"] = user.id
    request.session.regenerate_id()  # Neue ID!
```

#### 5. File Upload Exploits - "Der Malware-Schleuser"
**Was ist das?** Angreifer laden schädliche Dateien hoch.

**Unsere Verteidigung:**
```python
import magic
from pathlib import Path

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.jpg', '.png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/api/upload")
async def secure_upload(
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    # 1. Größe prüfen
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "Datei zu groß (max 10MB)")
    
    # 2. Extension prüfen
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Dateityp {ext} nicht erlaubt")
    
    # 3. MIME-Type prüfen (gegen Fake-Extensions)
    mime_type = magic.from_buffer(contents, mime=True)
    allowed_mimes = {
        'application/pdf', 
        'image/jpeg', 
        'image/png',
        'text/plain'
    }
    if mime_type not in allowed_mimes:
        raise HTTPException(400, "Ungültiger Dateiinhalt")
    
    # 4. Neuer sicherer Dateiname
    from uuid import uuid4
    safe_filename = f"{uuid4()}{ext}"
    
    # 5. In isoliertem Storage speichern
    await supabase.storage.upload(
        f"uploads/{user.id}/{safe_filename}",
        contents
    )
```

### Praktisches Security-Setup (Copy & Paste ready)

```python
# security.py - Einmal einrichten, immer sicher
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import secrets

def setup_security(app: FastAPI):
    """Komplettes Security-Setup in 5 Minuten"""
    
    # 1. Session Middleware (für sichere Cookies)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secrets.token_urlsafe(32),
        session_cookie="gustav_session",
        https_only=True,
        same_site="strict"
    )
    
    # 2. CORS (nur erlaubte Origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://gustav.de"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # 3. Host-Header Validation
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["gustav.de", "*.gustav.de", "localhost"]
    )
    
    # 4. Rate Limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    
    # 5. Security Headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=63072000",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "img-src 'self' data: https:;"
            )
        })
        return response

# In main.py einfach aufrufen:
from security import setup_security
app = FastAPI()
setup_security(app)
```

### Security-Checkliste für die Migration

#### Phase 1: Basis-Security (Tag 1 - 4h)
- [ ] Session Middleware einrichten (30min)
- [ ] CSRF-Schutz aktivieren (30min)
- [ ] Security Headers konfigurieren (30min)
- [ ] Basis-Auth mit sicheren Cookies (2h)
- [ ] Template Auto-Escaping prüfen (30min)

#### Phase 2: Erweiterte Security (Tag 2 - 4h)
- [ ] Input-Validierung mit Pydantic (1h)
- [ ] File Upload Validierung (2h)
- [ ] Rate Limiting implementieren (1h)

#### Phase 3: Monitoring & Auditing (Optional - 4h)
- [ ] Security-Event Logging
- [ ] Failed Login Tracking
- [ ] Anomalie-Erkennung
- [ ] Regular Security Audits planen

### Vergleich mit anderen Frameworks

| Sicherheitsfeature | Django | FastAPI+HTMX | Aufwand |
|-------------------|--------|--------------|---------|
| CSRF-Schutz | ✅ Automatisch | 🔧 30min Setup | Einmalig |
| XSS-Schutz | ✅ Automatisch | ✅ Automatisch | - |
| SQL Injection Schutz | ✅ ORM | ✅ Parametrized | - |
| Session Security | ✅ Eingebaut | 🔧 1h Setup | Einmalig |
| Rate Limiting | 📦 Package | 📦 Package | Gleich |

**Fazit:** Mit 8 Stunden einmaligem Aufwand haben wir eine maßgeschneiderte Security-Lösung, die genau auf unsere Bedürfnisse passt und keine unnötigen Abstraktionen enthält.

## Deployment & Operations

### Container Setup
```dockerfile
FROM python:3.11-slim
# Kein Node.js nötig!
# Keine Build-Steps!
# Nur Python Dependencies
```

### Monitoring
- Sentry für Error Tracking
- Prometheus Metrics via FastAPI
- Structured Logging (JSON)
- Health Check Endpoints

## Kosten-Nutzen-Analyse

### Einmalige Kosten
- Entwicklungszeit: ~3 Monate
- Keine zusätzlichen Infrastructure-Kosten
- Keine Lizenzkosten (alles Open Source)

### Langfristige Vorteile
- Reduzierte Wartungskosten
- Bessere Performance = weniger Server-Ressourcen
- Einfacheres Onboarding neuer Entwickler
- Zukunftssichere Technologie

## Authentifizierungs-Architektur

### Dual-Mode Authentication
Die Plattform unterstützt zwei parallele Authentifizierungsmethoden:

1. **Standard-Authentifizierung** (Primär)
   - Email/Password basiert
   - Selbstregistrierung möglich
   - Manuelle Gruppenzuordnung durch Admins
   - Volle Kontrolle über Nutzerdaten

2. **IServ SSO** (Optional)
   - Kann pro Installation aktiviert/deaktiviert werden
   - Automatische Gruppen-Synchronisation
   - Single Sign-On Komfort
   - Fallback auf Standard-Auth wenn IServ nicht verfügbar

### Login-Flow
```html
<!-- templates/pages/login.html -->
<div class="space-y-4">
  <!-- Standard Login immer verfügbar -->
  <form hx-post="/auth/login" class="space-y-4">
    <input type="email" name="email" placeholder="Email">
    <input type="password" name="password" placeholder="Passwort">
    <button type="submit">Anmelden</button>
  </form>
  
  <!-- IServ Button nur wenn aktiviert -->
  {% if iserv_enabled %}
  <div class="border-t pt-4">
    <a href="/auth/iserv/login" class="btn-secondary">
      Mit IServ anmelden
    </a>
  </div>
  {% endif %}
</div>
```

## Entscheidung

**Empfehlung:** Migration zu FastAPI + HTMX + Tailwind

**Begründung:**
1. Löst alle aktuellen Streamlit-Probleme
2. Minimaler Code, maximale Funktionalität
3. Keine Build-Prozesse oder Tooling-Komplexität
4. Perfekte Integration mit bestehender Infrastruktur
5. Moderne, schnelle User Experience
6. Flexible Authentifizierung (mit/ohne IServ)

## Nächste Schritte

1. **Management Buy-In** einholen
2. **PoC Development** (1 Woche)
   - Dashboard mit Auth implementieren
   - Performance messen
   - Team-Feedback sammeln
3. **Go/No-Go Entscheidung**
4. **Detailplanung** bei positivem Outcome

---

**Anhang: Code-Beispiele**

### Minimale FastAPI App
```python
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "user": user,
        "courses": await get_user_courses(user.id)
    })
```

### HTMX-powered Component
```html
<div hx-get="/api/notifications" 
     hx-trigger="every 30s"
     hx-swap="innerHTML">
    <!-- Auto-updating notifications -->
</div>
```

### Tailwind für moderne UI
```html
<div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <nav class="bg-white/80 backdrop-blur-md shadow-sm">
        <!-- Glassmorphism effect -->
    </nav>
</div>
```

### Admin Interface für Nutzerverwaltung
```html
<!-- templates/pages/admin/users.html -->
<div class="max-w-6xl mx-auto p-6">
  <h1 class="text-2xl font-bold mb-6">Nutzerverwaltung</h1>
  
  <!-- User-Tabelle mit manueller Gruppenzuordnung -->
  <div class="bg-white rounded-lg shadow">
    {% for user in users %}
    <div class="p-4 border-b flex justify-between items-center">
      <div>
        <h3 class="font-medium">{{ user.name }}</h3>
        <p class="text-sm text-gray-600">{{ user.email }}</p>
        <p class="text-xs text-gray-500">
          Anmeldung: {% if user.iserv_id %}IServ{% else %}Standard{% endif %}
        </p>
      </div>
      
      <!-- Manuelle Gruppenzuordnung -->
      <form hx-post="/api/users/{{ user.id }}/groups" 
            hx-target="#groups-{{ user.id }}">
        <select name="group_id" class="border rounded px-3 py-1">
          <option value="">Gruppe zuordnen...</option>
          {% for group in available_groups %}
          <option value="{{ group.id }}">{{ group.name }}</option>
          {% endfor %}
        </select>
        <button type="submit" class="ml-2 px-4 py-1 bg-blue-600 text-white rounded">
          Zuordnen
        </button>
      </form>
      
      <div id="groups-{{ user.id }}" class="text-sm">
        {% for group in user.groups %}
        <span class="px-2 py-1 bg-gray-100 rounded">{{ group.name }}</span>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>
</div>
```