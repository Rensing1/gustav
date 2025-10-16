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

- Dienste: Keycloak läuft im Compose auf `http://localhost:8080` (Realm‑Import via `keycloak/realm-gustav.json`).
- Der Web‑Adapter (FastAPI) nutzt OIDC Authorization Code Flow mit PKCE. In PROD erfolgen `/auth/login|register|forgot` als Redirect zur Keycloak‑UI.
- Optional (DEV/CI): Eigene HTML‑Formulare sind per Feature‑Flag aktivierbar (`AUTH_USE_DIRECT_GRANT=true`). Login per Password‑Grant, Registration via Admin‑API. Siehe `docs/ARCHITECTURE.md` → „Auth UI (Phase 1 – DEV/CI)“.
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

## Tests

- Unit/Contract‑Tests laufen mit `pytest` gegen die ASGI‑App (`httpx` + `ASGITransport`).
- E2E‑Test (Keycloak ↔ GUSTAV) unter `backend/tests_e2e/test_identity_login_register_logout_e2e.py` (setzt laufendes `docker compose up -d keycloak web` voraus).
- Ausführen:
  - Alle Tests: `.venv/bin/pytest -q`
  - E2E fokussiert: `.venv/bin/pytest -q backend/tests_e2e/test_identity_login_register_logout_e2e.py`
  

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
