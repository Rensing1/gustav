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
