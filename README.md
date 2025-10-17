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
- Hinweis: Eigene HTML‑Formulare (Direct‑Grant) wurden entfernt. Alle Flows laufen über die Keycloak‑UI (Authorization‑Code‑Flow mit PKCE).
- Keycloak‑Theme (GUSTAV‑Look): Ein schlankes CSS‑Theme liegt unter `keycloak/themes/gustav` und wird beim Image‑Build in den Keycloak‑Container kopiert. Der Realm ist so vorkonfiguriert, dass das Theme genutzt wird (`loginTheme: "gustav"`).

### Verhalten & Sicherheit
- Login‑Erzwingung (Middleware):
  - HTML ohne Session → `302` nach `/auth/login`
  - API/JSON ohne Session → `401` JSON + `Cache-Control: no-store`
  - HTMX ohne Session → `401` + `HX-Redirect: /auth/login`
  - Allowlist: `/auth/*`, `/health`, `/static/*`, `/favicon.ico`
- Callback‑Fehler (`/auth/callback`) setzen immer `Cache-Control: no-store`.
- `/auth/login` akzeptiert keinen client‑seitigen `state`; dieser wird serverseitig erzeugt.
- Redirect‑Parameter sind nur als interne absolute Pfade erlaubt (kein externer Redirect).
- Unified Logout: `GET /auth/logout` löscht das App‑Session‑Cookie und leitet zum IdP End‑Session Endpoint; nach Rückkehr geht es standardmäßig zur Erfolgsseite (`/auth/logout/success`). Optional kann ein interner absoluter Pfad per `redirect` angegeben werden (z. B. `/courses`). Falls vorhanden, wird `id_token_hint` übergeben.

Vorschau Keycloak‑Theme:
- Starten: `docker compose up -d`
- Hosts‑Eintrag (einmalig, lokal):
  - `/etc/hosts` → `127.0.0.1 app.localhost id.localhost`
- App: `http://app.localhost:8100`
- Login (Keycloak): `http://id.localhost:8100/realms/gustav/account/` → „Anmelden“
- Die Loginseite sollte farblich/typografisch zu GUSTAV passen.
- Konfiguration über Umgebungsvariablen (siehe `.env`):
  - `KC_BASE_URL` (default: `http://keycloak:8080` im Compose)
  - `KC_PUBLIC_BASE_URL` (default: `http://id.localhost:8100`)
  - `KC_REALM` (default: `gustav`)
  - `KC_CLIENT_ID` (default: `gustav-web`)
  - `REDIRECT_URI` (default: `http://app.localhost:8100/auth/callback`)
  - (optional) Admin‑Zugangsdaten für Keycloak nur für manuelle Administration
- Cookies: httpOnly Session‑Cookie `gustav_session` (opaque ID). In Prod zusätzlich `Secure` und `SameSite=strict`; in Dev `SameSite=lax`.
- Sicherheit: ID‑Token wird gegen JWKS verifiziert (Issuer/Audience/Expiry), Rollen werden restriktiv gemappt (`student|teacher|admin`).

### Theme anpassen (lokal)
- Dateien:
  - Templates: `keycloak/themes/gustav/login/{login.ftl,register.ftl,login-reset-password.ftl}`
  - Styles: `keycloak/themes/gustav/login/resources/css/gustav.css`
  - Gemeinsames Basis‑CSS: Das kanonische App‑CSS `backend/web/static/css/gustav.css` wird beim Keycloak‑Image‑Build als `keycloak/themes/gustav/login/resources/css/app-gustav-base.css` mitkopiert. So greifen IdP‑Seiten und App auf dieselben Variablen/Komponenten zu – ohne Volumes.
  - DE‑Texte: `keycloak/themes/gustav/login/messages/messages_de.properties`
- Realm‑Konfiguration (Default DE): `keycloak/realm-gustav.json:1`
  - `loginTheme: "gustav"`, `internationalizationEnabled: true`, `defaultLocale: "de"`
- Änderungen wirken nach `docker compose up -d --build caddy web keycloak` (Keycloak lädt Theme beim Start).

## Tests

- Unit/Contract‑Tests laufen mit `pytest` gegen die ASGI‑App (`httpx` + `ASGITransport`).
- E2E (Keycloak ↔ GUSTAV) ist Teil der Suite: Login/Logout sowie Registrierungs‑Validierungen.
  - Login/Logout: `backend/tests_e2e/test_identity_login_register_logout_e2e.py`
  - Registrierung (Fehlerfälle: fehlende Felder, ungültige E‑Mail, schwaches Passwort, Passwort‑Bestätigung ungleich, Duplicate‑E‑Mail): `backend/tests_e2e/test_identity_register_validation_e2e.py`
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
