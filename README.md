# GUSTAV alpha‑2 – Moderne Lernplattform

KI‑gestützte Lernplattform mit FastAPI und HTMX. Server‑seitiges Rendern (SSR) mit eigenen Python‑Komponenten, ohne externe CSS‑Frameworks.

## Schnellstart

- Voraussetzungen
  - Docker & Docker Compose installiert
  - Port `8100` ist frei

- Starten
  - Projekt bauen: `docker compose build`
  - Starten: `docker compose up`
  - Öffnen: `http://localhost:8100`

- Entwicklung (Live‑Reload)
  - Volume ist auf `backend/web` gemountet, Änderungen werden erkannt
  - Uvicorn reloadet automatisch; kein manueller Neustart nötig

- Nützliche Befehle
  - Hintergrund: `docker compose up -d`
  - Logs: `docker compose logs -f`
  - Stoppen: `docker compose down`
  - Neu bauen (nach `requirements.txt`‑Änderung): `docker compose build --no-cache`

## Struktur

```
gustav-alpha2/
├── api/
│   └── openapi.yml          # API-Vertrag (Contract-First)
├── backend/
│   └── web/                 # Web-Adapter (FastAPI, SSR, HTMX)
│       ├── main.py          # Routen, Seitenaufbau
│       ├── components/      # UI-Komponenten
│       ├── static/          # CSS/JS/Assets
│       └── requirements.txt # Python-Dependencies
├── docs/
│   ├── ARCHITECTURE.md      # Überblick Architektur und Vorgehen
│   ├── glossary.md          # Begriffe
│   ├── bounded_contexts.md  # Kontextzuschnitte
│   ├── database_schema.md   # DB-Schema (Platzhalter)
│   └── UI-UX-Leitfaden.md   # UI/UX-Richtlinien
├── docker-compose.yml
├── Dockerfile
└── legacy-code-alpha1/
```

Siehe auch: `docs/ARCHITECTURE.md:1` für Schichten, Flows und Migrationspfad.

## Auth (Keycloak) lokal

- Dienste: Keycloak läuft im Compose (Realm‑Import via `keycloak/realm-gustav.json`).
- Der Web‑Adapter (FastAPI) nutzt OIDC Authorization Code Flow mit PKCE. In PROD erfolgen `/auth/login|register|forgot` als Redirect zur Identity‑UI.
- Optional (DEV/CI): Eigene HTML‑Formulare sind per Feature‑Flag aktivierbar (`AUTH_USE_DIRECT_GRANT=true`). Login per Password‑Grant, Registration via Admin‑API. Siehe `docs/ARCHITECTURE.md` → „Auth UI (Phase 1 – DEV/CI)“.
- Keycloak‑Theme (GUSTAV‑Look): Ein schlankes CSS‑Theme ist unter `keycloak/themes/gustav` enthalten und wird per Compose in den Container gemountet. Der Realm ist so vorkonfiguriert, dass das Theme genutzt wird (`loginTheme: "gustav"`).

Vorschau Keycloak‑Theme:
- Starten: `docker compose up -d`
- Hosts‑Eintrag (einmalig, lokal):
  - `/etc/hosts` → `127.0.0.1 app.localhost id.localhost`
- App: `http://app.localhost:8100`
- Login (Keycloak): `http://id.localhost:8100/realms/gustav/account/` → „Anmelden“
- Die Loginseite sollte farblich/typografisch zu GUSTAV passen.
- Konfiguration über Umgebungsvariablen (siehe `.env`):
  - `KC_BASE_URL` (default: `http://localhost:8080`)
  - `KC_PUBLIC_BASE_URL` (default: `http://localhost:8080`)
  - `KC_REALM` (default: `gustav`)
  - `KC_CLIENT_ID` (default: `gustav-web`)
  - `REDIRECT_URI` (default: `http://localhost:8100/auth/callback`)
  - `AUTH_USE_DIRECT_GRANT` (DEV/CI: `true` um SSR‑Formulare zu nutzen)
  - (DEV/CI Registrierung) `KC_ADMIN_USERNAME`, `KC_ADMIN_PASSWORD`
- Cookies: httpOnly Session‑Cookie `gustav_session` (opaque ID). In Prod zusätzlich `Secure` und `SameSite=strict`; in Dev `SameSite=lax`.
- Sicherheit: ID‑Token wird gegen JWKS verifiziert (Issuer/Audience/Expiry), Rollen werden restriktiv gemappt (`student|teacher|admin`).

### Theme anpassen (lokal)
- Dateien:
  - Templates: `keycloak/themes/gustav/login/templates/{login.ftl,register.ftl,login-reset-password.ftl}`
  - Styles: `keycloak/themes/gustav/login/resources/css/gustav.css`
  - DE‑Texte: `keycloak/themes/gustav/login/messages/messages_de.properties`
- Realm‑Konfiguration (Default DE): `keycloak/realm-gustav.json:1`
  - `loginTheme: "gustav"`, `internationalizationEnabled: true`, `defaultLocale: "de"`
- Änderungen wirken nach `docker compose up -d --build caddy web keycloak` (Keycloak lädt Theme beim Start).

## Tests

- Unit/Contract‑Tests laufen mit `pytest` gegen die ASGI‑App (`httpx` + `ASGITransport`).
- E2E (Keycloak ↔ GUSTAV) ist Teil der Suite: `backend/tests_e2e/test_identity_login_register_logout_e2e.py`.
- Voraussetzungen für E2E: `docker compose up -d caddy web keycloak` und Hosts‑Eintrag `127.0.0.1 app.localhost id.localhost`.
- Ausführen:
  - Alle Tests inkl. E2E: `.venv/bin/pytest -q`
  - Nur E2E: `RUN_E2E=1 WEB_BASE=http://app.localhost:8100 KC_BASE=http://id.localhost:8100 .venv/bin/pytest -q -m e2e`
  

## Entwicklungs-Workflow

- Contract‑First
  - Änderungen zuerst in `api/openapi.yml:1`
  - BDD‑Szenarien (Given‑When‑Then) formulieren
  - pytest‑Tests schreiben, dann minimal implementieren (Red‑Green‑Refactor)

- TDD
  - Tests unter `backend/tests/` (wird schrittweise aufgebaut)
  - Externe Abhängigkeiten mocken, gegen lokale Test‑DB prüfen

- Branch‑Strategie
  - `main`: stabil, release‑bereit
  - `development`: aktiver Entwicklungszweig (Standard)
  - Feature‑Branches: `feat/<kurz-beschreibung>`, Bugfix: `fix/<issue-nummer-oder-thema>`
  - PRs nach `development`, regelmäßiges Merge nach `main`

## Technologie-Stack

- Backend: FastAPI (Python 3.11), Uvicorn
- SSR/Interaktivität: Eigene Komponenten + HTMX (`backend/web/static/js/vendor/htmx.min.js`)
- Styling: Custom CSS (`backend/web/static/css/gustav.css`)
- Container: Docker & Docker Compose
- Datenbank (geplant): PostgreSQL via Supabase (Migrationen später unter `supabase/migrations/`)
- KI (geplant): Ollama + DSPy

## Hinweise zur UI-Entwicklung

- CSS
  - Keine externen CDN/Frameworks → DSGVO‑konform, KISS
  - Fokus auf Lesbarkeit und Lehrbarkeit

- Komponenten
  - UI wird in Python‑Komponenten strukturiert (`backend/web/components/`)
  - Seiten werden in `main.py` zusammengesetzt

## Healthcheck

- Endpoint: `GET /health` → `{"status": "healthy", "service": "gustav-v2"}`

## Weiterführende Dokumentation

- Architektur: `docs/ARCHITECTURE.md:1`
- Begriffe: `docs/glossary.md:1`
- Bounded Contexts: `docs/bounded_contexts.md:1`
- DB‑Schema (Übersicht/Platzhalter): `docs/database_schema.md:1`
