# GUSTAV Migration Prompt für Claude

## Kontext & Ziel
Du hilfst bei der schrittweisen Migration von GUSTAV von Streamlit zu FastAPI + HTMX + Tailwind CSS. Die Migration erfolgt in kleinen, testbaren Schritten mit Fokus auf Einfachheit und Wartbarkeit.

## Kritische Architektur-Überlegungen

### Auth-Service: BEIBEHALTEN mit Anpassungen ✅

**Gründe für Beibehaltung:**
- Separater Auth-Service ist architektonisch sauber (Single Responsibility)
- HttpOnly Cookies bereits implementiert
- Session Management über Supabase SQL Functions funktioniert gut
- CSRF-Schutz vorhanden
- Security Headers bereits konfiguriert

**Notwendige Anpassungen:**
1. Login/Register Pages von Streamlit auf HTMX Templates migrieren
2. Auth-Endpoints für HTMX optimieren (HTML-Fragmente statt JSON)
3. Session-Validation Middleware für FastAPI schreiben
4. Cookie-Settings für neue Domain anpassen

### Nginx: VEREINFACHEN & MODERNISIEREN ⚡

**Aktuelle Probleme:**
- Komplexe Lua-Scripts für WebSocket Auth
- Zu viele Security-Header in nginx (besser in FastAPI)
- Rate-Limiting besser in FastAPI (mehr Kontrolle)
- SSL-Termination gut, aber Rest überdimensioniert

**Neue Strategie:**
```nginx
# Minimaler nginx - nur als Reverse Proxy & SSL
server {
    listen 443 ssl http2;

    # SSL Config (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/...;

    # Einfaches Proxying
    location / {
        proxy_pass http://fastapi:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSockets für HTMX SSE
    location /events {
        proxy_pass http://fastapi:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Migration Roadmap (Phasenweise)

### Phase 0: Vorbereitung (Du bist hier!)
```
1. FastAPI Projekt-Struktur aufsetzen
2. Basis-Templates mit HTMX/Tailwind
3. Auth-Service Integration vorbereiten
```

### Phase 1: Login & Basis-UI ← START HIER
```
Ziel: Funktionierender Login mit Cookie-Auth und erstes Dashboard
```

### Phase 2: Core Features
```
Kurse, Aufgaben, Abgaben (Read-Only erst)
```

### Phase 3: Interaktive Features
```
File Upload, KI-Chat, Feedback
```

## Der strukturierte Claude-Prompt

```markdown
# GUSTAV Migration Assistant

Ich arbeite an der Migration von GUSTAV (Lernplattform) von Streamlit zu FastAPI+HTMX+Tailwind.

## Aktueller Status
- [ ] FastAPI Grundstruktur
- [ ] Template-System (Jinja2)
- [ ] HTMX Integration
- [ ] Tailwind CSS Setup
- [ ] Auth-Service Anbindung
- [ ] Login-Flow
- [ ] Dashboard

## Projekt-Struktur
```
gustav-v2/
├── app/
│   ├── main.py              # FastAPI App
│   ├── routes/              # Endpoints
│   │   ├── auth.py         # Auth Integration
│   │   ├── pages.py        # HTML Pages
│   │   └── api.py          # HTMX Endpoints
│   ├── templates/
│   │   ├── base.html       # Layout
│   │   ├── pages/          # Full Pages
│   │   └── components/     # HTMX Fragmente
│   ├── static/             # Assets
│   ├── middleware/         # Auth, Security
│   └── dependencies.py     # Shared Deps
├── auth_service/           # EXISTING - behalten!
├── nginx/                  # VEREINFACHEN
└── docker-compose.yml      # ANPASSEN
```

## Aktuelle Aufgabe
[BESCHREIBE HIER DEINE AKTUELLE AUFGABE]

## Code-Prinzipien
1. **Keine Build-Tools** - Alles via CDN
2. **Server-Side First** - HTML vom Server, HTMX für Updates
3. **Cookies statt LocalStorage** - HttpOnly für Security
4. **Progressiv Enhancement** - Funktioniert ohne JS
5. **Semantic HTML** - Accessibility first

## Security Checklist
- [ ] CSRF Token in Forms
- [ ] XSS: Template Auto-Escape aktiv?
- [ ] SQL: Parametrisierte Queries
- [ ] Cookies: HttpOnly, Secure, SameSite
- [ ] Headers: CSP, HSTS, X-Frame-Options

## HTMX Patterns

### Form Submit
```html
<form hx-post="/submit"
      hx-target="#result"
      hx-swap="outerHTML">
    {% csrf_token %}
    <input name="data">
    <button>Submit</button>
</form>
```

### Live Update
```html
<div hx-get="/status"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
    Loading...
</div>
```

### File Upload
```html
<form hx-post="/upload"
      hx-encoding="multipart/form-data">
    <input type="file" name="file">
</form>
```

## FastAPI Patterns

### Template Response
```python
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "pages/home.html",
        {"request": request, "user": get_user(request)}
    )
```

### HTMX Fragment
```python
@app.post("/tasks/{id}/complete")
async def complete_task(id: int):
    task = complete_task_in_db(id)
    return templates.TemplateResponse(
        "components/task_card.html",
        {"task": task}
    )
```

### Auth Dependency
```python
async def require_user(request: Request):
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(401)
    user = verify_token(token)
    return user

@app.get("/protected")
async def protected(user=Depends(require_user)):
    return {"user": user}
```

## Hilf mir bei
[SPEZIFISCHE FRAGE/PROBLEM]
```

## Implementierungs-Reihenfolge für Phase 1

### Schritt 1: FastAPI Basis aufsetzen
```python
# main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="GUSTAV v2")
templates = Jinja2Templates(directory="templates")

# Health Check
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Home Route
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("pages/home.html", {
        "request": request,
        "title": "GUSTAV - Willkommen"
    })
```

### Schritt 2: Base Template mit HTMX/Tailwind
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}GUSTAV{% endblock %}</title>

    <!-- Tailwind CSS via CDN -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>

    <!-- Alpine.js für lokale Interaktivität (optional) -->
    <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>

    {% block head %}{% endblock %}
</head>
<body class="bg-gray-50">
    {% block content %}{% endblock %}

    <!-- HTMX Config -->
    <script>
        document.body.addEventListener('htmx:configRequest', (e) => {
            // CSRF Token automatisch mitsenden
            const token = document.querySelector('meta[name="csrf-token"]')?.content;
            if (token) {
                e.detail.headers['X-CSRFToken'] = token;
            }
        });
    </script>
</body>
</html>
```

### Schritt 3: Login Page
```html
<!-- templates/pages/login.html -->
{% extends "base.html" %}

{% block content %}
<div class="min-h-screen flex items-center justify-center">
    <div class="max-w-md w-full space-y-8">
        <div>
            <h2 class="text-3xl font-bold text-center">Anmelden</h2>
        </div>

        <form hx-post="/auth/login"
              hx-target="#login-result"
              class="space-y-6">

            <div>
                <label for="email" class="block text-sm font-medium">
                    Email
                </label>
                <input type="email"
                       name="email"
                       required
                       class="mt-1 block w-full rounded-md border-gray-300">
            </div>

            <div>
                <label for="password" class="block text-sm font-medium">
                    Passwort
                </label>
                <input type="password"
                       name="password"
                       required
                       class="mt-1 block w-full rounded-md border-gray-300">
            </div>

            <button type="submit"
                    class="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Anmelden
            </button>
        </form>

        <div id="login-result"></div>
    </div>
</div>
{% endblock %}
```

### Schritt 4: Auth Integration
```python
# routes/auth.py
from fastapi import APIRouter, Request, Response, Form
from typing import Optional
import httpx

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    # Forward to auth service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://auth:8000/auth/login",
            json={"email": email, "password": password}
        )

        if response.status_code == 200:
            data = response.json()

            # Set cookie from auth service
            resp = templates.TemplateResponse(
                "components/login_success.html",
                {"request": request}
            )
            resp.set_cookie(
                key="auth_token",
                value=data["token"],
                httponly=True,
                secure=True,
                samesite="lax"
            )
            # HTMX redirect via header
            resp.headers["HX-Redirect"] = "/dashboard"
            return resp
        else:
            return templates.TemplateResponse(
                "components/login_error.html",
                {"request": request, "error": "Login fehlgeschlagen"}
            )
```

## Docker Compose Anpassungen

```yaml
# docker-compose.yml (neu)
services:
  app:
    build: ./app-v2
    container_name: gustav_app_v2
    ports:
      - "8000:8000"
    volumes:
      - ./app-v2:/app
    env_file:
      - .env
    environment:
      - AUTH_SERVICE_URL=http://auth:8000
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000
    networks:
      - gustav_network

  auth:
    # BLEIBT UNVERÄNDERT
    build: ./auth_service
    # ...

  nginx:
    # VEREINFACHT - neue Config
    # ...
```

## Wichtige Entscheidungen

### Was wir BEHALTEN
- Auth-Service (FastAPI) ✅
- Supabase als Backend ✅
- Docker-basiertes Deployment ✅
- Let's Encrypt SSL ✅

### Was wir ÄNDERN
- Streamlit → FastAPI + HTMX ⚡
- Complex nginx → Simple Reverse Proxy 🎯
- Client-side State → Server-side Sessions 🔒
- Build Process → CDN-only 🚀

### Was wir HINZUFÜGEN
- Jinja2 Templates 📄
- HTMX für Interaktivität 🔄
- Tailwind für Styling 🎨
- Server-Sent Events für Realtime 📡

---

## Start-Command für Claude:
"Hilf mir, die FastAPI Basis-Struktur mit Templates für GUSTAV-alpha2 aufzusetzen. Beginne mit main.py und der Ordnerstruktur."