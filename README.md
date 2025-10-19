# GUSTAV alpha‑2 – Moderne Lernplattform

KI‑gestützte Lernplattform mit FastAPI und HTMX. Server‑seitiges Rendern (SSR) mit eigenen Python‑Komponenten.

## Schnellstart

- Voraussetzungen: Docker & Docker Compose, Port `8100` frei
- Start: `docker compose build && docker compose up`
- Öffnen: `http://localhost:8100`
- Entwicklung: Live‑Reload für `backend/web` ist aktiv
- Nützlich: `docker compose up -d`, `docker compose logs -f`, `docker compose down`

## Projektstruktur (Kurz)

```
gustav-alpha2/
├── api/                 # OpenAPI-Vertrag
├── backend/web/         # FastAPI, SSR, Komponenten, Static
├── docs/                # Architektur, Pläne, Leitfäden
├── docker-compose.yml
└── Dockerfile
```

## Tests

- Ausführen: `.venv/bin/pytest -q`

## Contributing

- Arbeitsweise: Contract‑First, TDD (Red‑Green‑Refactor)
- Bitte Hinweise in `docs/ARCHITECTURE.md` und `docs/plan/README.md` beachten
- Branch‑Strategie: `development` (aktiv), PRs gegen `development`

## Healthcheck

- `GET /health` → `{ "status": "healthy", "service": "gustav-v2" }`

## Dokumentation

- Architektur: `docs/ARCHITECTURE.md`
- Glossar: `docs/glossary.md`
- Bounded Contexts: `docs/bounded_contexts.md`
- UI/UX: `docs/UI-UX-Leitfaden.md`
- Datenbank: `docs/database_schema.md`
- Lizenz: `docs/LICENCE.md`

## Identity & Sessions (Kurzüberblick)

- IdP: Keycloak (OIDC Authorization Code Flow mit PKCE)
- Session-Cookie: `gustav_session` (httpOnly)
- Umgebungsvariablen:
  - `GUSTAV_ENV`: `dev` (Default) oder `prod` → steuert Cookie-Flags (`Secure`, `SameSite`)
  - `SESSIONS_BACKEND`: `memory` (Default) oder `db` (Postgres/Supabase)
  - `DATABASE_URL` (oder `SUPABASE_DB_URL`): DSN für DB-gestützte Sessions
  - `REDIRECT_URI`: Muss auf `/auth/callback` der App zeigen; wird zur Berechnung des App‑Basis‑URLs genutzt (Logout‑Redirect)
