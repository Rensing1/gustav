# GUSTAV Architektur (alpha‑2)

Dieses Dokument beschreibt die aktuelle Architektur von GUSTAV (Stand: alpha‑2) sowie den geplanten Ausbau. Ziel ist eine verständliche, lehrbare Struktur gemäß unseren Projektprinzipien: KISS, Security‑first, FOSS, Clean Architecture, API Contract‑First und TDD (Red‑Green‑Refactor).

## Ziele und Leitlinien
- KISS & Lesbarkeit: Code ist einfach, nachvollziehbar und gut kommentiert.
- Security‑first: Minimalprinzip, DSGVO‑Konformität, spätere RLS‑Durchsetzung auf DB‑Ebene.
- Contract‑First: Änderungen an der API beginnen im Vertrag `api/openapi.yml:1`.
- TDD: Erst Tests (pytest), dann minimaler Code, dann Refactor.
- Clean Architecture: Fachlogik getrennt von Frameworks (FastAPI, Supabase, etc.).

## High‑Level Komponenten
- Web‑Adapter (`backend/web/`): FastAPI mit serverseitigem Rendern (SSR) und HTMX für progressive Interaktivität. Enthält aktuell Routen, UI‑Komponenten und statische Assets.
- API‑Vertrag (`api/openapi.yml:1`): Quelle der Wahrheit für öffentliche Endpunkte. Tests validieren Verhalten gegen den Vertrag.
- Datenbank (geplant): PostgreSQL via Supabase; Migrationen später unter `supabase/migrations/` verwaltet.
- Legacy‑Code: `legacy-code-alpha1/` bleibt Referenz, wird aber nicht direkt erweitert.

## Schichten (Clean Architecture)
1) Domain (geplant)
   - Entities, Value Objects, Domain Events
   - Framework‑frei, nur reine Python‑Logik
2) Application / Use Cases (geplant)
   - Orchestriert Use Cases, Ports/Interfaces zu Infrastruktur
   - Keine Kenntnis von FastAPI/HTTP
3) Interface Adapters (heute)
   - `backend/web/` als Web‑Adapter (FastAPI, SSR, HTMX)
   - Übersetzt HTTP <-> Use Cases (sobald vorhanden)
4) Frameworks & Drivers (heute)
   - FastAPI, Uvicorn, später Supabase SDK, Redis für Sessions

Diese Trennung wird inkrementell umgesetzt. Aktuell befindet sich noch UI‑naher Code im Web‑Adapter, Use Cases sind noch nicht extrahiert.

## Bounded Contexts (Domänenzuschnitte)
Geplant (siehe `docs/bounded_contexts.md:1`):
- `identity_access`: Nutzer, Rollen, AuthN/AuthZ (IServ/Supabase)
- `teaching`: Kurse, Lerneinheiten, Abschnitte, Freischaltung, Live-Unterrichts-Ansicht
- `learning`: Einreichungen, Aufgaben, Karteikarten (Spaced Repetition)
- `analytics`: Berichte, Learning Analytics Dashboard
- `core`: geteilte Basistypen (IDs, Zeit, Fehler, Policies)

Im Code spiegeln sich diese Kontexte perspektivisch als Pakete unter `backend/` wider. Startpunkt ist aktuell der Web‑Adapter; die Extraktion der Use Cases folgt, sobald erste API‑Funktionen entstehen.

## Ordnerstruktur (aktuell)
- `api/openapi.yml` – API‑Vertrag (Contract‑First)
- `backend/web/` – Web‑Adapter (FastAPI, SSR/HTMX)
  - `main.py` – Routen und Seitenaufbau
  - `components/` – UI‑Bausteine
  - `static/` – CSS/JS/Assets
  - `models/` – vorläufige UI‑Modelle/Mocks
- `docs/` – Projektdokumentation
  - `glossary.md` – Begriffe (bitte konsistent mit API/DB nutzen)
  - `bounded_contexts.md` – Kontextzuschnitte
  - `database_schema.md` – Schema (derzeit leer; geplant über Migrationen zu füllen)
  - `UI-UX-Leitfaden.md` – Richtlinien für Gestaltung/Interaktionen
- `Dockerfile`, `docker-compose.yml` – Containerisierung (Dev‑Setup)
- `legacy-code-alpha1/` – Referenz Altcode

Geplante Ergänzungen (separat anlegen, wenn benötigt):
- `supabase/migrations/` – SQL‑Migrationen (via Supabase CLI)
- `backend/tests/` – pytest‑Tests für API/Use Cases
- `docs/ROADMAP.md`, `docs/CHANGELOG.md`, `docs/LICENCE.md`, `docs/science/*`, `docs/plan/*`

## Request‑Flow (heute)
1) Browser sendet Request an FastAPI (`backend/web/main.py:1`).
2) Web‑Adapter rendert HTML (SSR) mit Komponenten und liefert statische Assets aus.
3) HTMX nutzt Teilaktualisierungen, bleibt aber servergetrieben (kein volles SPA‑Bundle nötig).

Sobald Use Cases extrahiert sind: Route -> DTO/Command -> Use Case -> Port -> Adapter/Repo -> Response DTO -> Presenter/View.

## API Contract‑First (Vorgehen)
1) API‑Änderung zuerst im Vertrag: `api/openapi.yml:1`.
2) BDD‑Szenarien formulieren (Given‑When‑Then).
3) pytest‑Test gegen die definierte Spezifikation schreiben (lokale Test‑DB, externe Abhängigkeiten mocken).
4) Minimalen Code implementieren (Web‑Adapter + Use Case), bis der Test grün ist.
5) Refactoring: Aufräumen, Entkopplung, Performance/Security prüfen.

## Sicherheit & Datenschutz (Grundsätze)
- AuthN/A: Supabase/IServ (Single Sign‑On) – Implementierung folgt.
- DB‑Zugriff: RLS‑Prinzip (Row Level Security) – Architektur bereitet darauf vor.
- PII‑Minimierung: Nur notwendige personenbezogene Daten speichern.
- Cookies: httpOnly, Secure, SameSite; CSRF‑Schutz bei Formularen.
- CORS: Nicht nötig in SSR‑Setup (gleiche Origin); bei zukünftiger SPA strikt konfigurieren.
- Logging: Keine sensiblen Inhalte; zweckgebundenes Monitoring.

## Datenbank & Migrationen (geplant)
- PostgreSQL (Supabase). Migrationen als versionierte SQL‑Dateien unter `supabase/migrations/`.
- Namenskonventionen: snake_case Tabellen/Spalten, Präfixe pro Kontext (z. B. `learning_submissions`).
- Test‑DB: Separate Testumgebung für pytest, Transaktions‑Rollback/Fixture‑Strategie.

## Tests & Qualität (TDD)
- Speicherort Tests: `backend/tests/` (API‑Tests, Use‑Case‑Tests, Adapter‑Tests)
- Philosophie: Spezifikationsnahe Tests, klein anfangen, dann breiter testen.
- Tools: pytest, httpx TestClient, Factory‑Fixtures; Lint/Format analog Repo‑Standards (später).

## Deployment & Betrieb
- Containerisiert über `Dockerfile` und `docker-compose.yml`.
- Entwicklungsstart: `docker compose up --build` (Hot‑reload aktiv).
- Healthcheck: `GET /health` für einfache Verfügbarkeitsprüfung.

## Migrationspfad zu einer getrennten SPA (optional)
Wenn UI‑Anforderungen wachsen (Offline, State‑heavy, App‑Store), kann ein separates `frontend/` entstehen. Schritte:
1) API aus SSR‑Routen herauslösen, strikt nach Vertrag (`api/openapi.yml`).
2) Auth‑Flow und CORS für Mehr‑Origin konfigurieren.
3) SSR weiter für Server‑Seiten oder reine API fahren; SPA konsumiert JSON.

## Zusammenarbeit & Dokumentation
- Begriffe konsistent mit `docs/glossary.md:1` verwenden.
- Kontextzuschnitte aus `docs/bounded_contexts.md:1` beachten.
- DB‑Änderungen synchron zu `docs/database_schema.md:1` dokumentieren (generiert aus Migrationen oder manuell als Übersicht).
- Größere Änderungen vorab in `docs/plan/` skizzieren; Ergebnisse und Entscheidungen nachvollziehbar halten.

