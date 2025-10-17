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

### Identity & Auth – vereinfachte Integration (DEV/PROD)

- DEV (hostbasiert, einfach & robust):
  - Caddy routet hostbasiert:
    - `http://app.localhost:8100` → Web (GUSTAV)
    - `http://id.localhost:8100` → Keycloak (IdP)
  - Vorteil: keine Pfadpräfixe/Rewrite‑Komplexität, korrekte Hostname‑Links, klare Trennung.
  - Setup: `/etc/hosts` → `127.0.0.1 app.localhost id.localhost`.
- PROD (Security‑first, geringe App‑Komplexität):
  - `/auth/login|register|forgot` leiten zur gebrandeten Keycloak‑UI (Authorization‑Code‑Flow mit PKCE).
  - GUSTAV verarbeitet keine Passwörter; Sessions sind serverseitig und über `gustav_session` gesichert.

#### Keycloak Theme (GUSTAV)
- Pfad: `keycloak/themes/gustav/login`
  - Templates: `templates/login.ftl`, `templates/register.ftl`, `templates/login-reset-password.ftl`
  - Styles: `resources/css/gustav.css` (kompaktes Layout über .kc‑* Klassen)
  - i18n: `messages/messages_de.properties` (DE‑Texte)
- Realm‑Konfiguration: `keycloak/realm-gustav.json:1`
  - `loginTheme: "gustav"`, `internationalizationEnabled: true`, `defaultLocale: "de"`, `supportedLocales: ["de","en"]`

#### DEV‑Flag (optional)
- `AUTH_USE_DIRECT_GRANT=true` aktiviert SSR‑Formulare in DEV/CI (TDD & UI‑Prototyping).
- CSRF: Double‑Submit via Cookie `gustav_csrf` + hidden `csrf_token`.
- Nicht für PROD gedacht.

#### Ablauf Authorization‑Code‑Flow
1) Browser: `GET /auth/login` (GUSTAV) → 302 zu IdP `…/protocol/openid-connect/auth` (Host: `id.localhost`).
2) Login auf IdP‑UI (gebrandet). Registrierung führt in Keycloak zu einer aktiven Session (Auto‑Login), sofern keine Verifizierung verlangt wird.
3) IdP → Redirect zu `REDIRECT_URI` (z. B. `http://app.localhost:8100/auth/callback`).
4) Web tauscht Code gegen Tokens am internen Token‑Endpoint (`KC_BASE_URL`) und verifiziert das ID‑Token.
5) Web legt Serversession an und setzt `gustav_session` (httpOnly; in DEV SameSite=lax, in PROD strict + Secure).

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

E2E‑Tests (Identity):
- Testdatei: `backend/tests_e2e/test_identity_login_register_logout_e2e.py`
- Voraussetzung: `docker compose up -d caddy web keycloak` und Hosts‑Eintrag `127.0.0.1 app.localhost id.localhost`.
- Ausführung:
  - Alle Tests inkl. E2E: `.venv/bin/pytest -q`
  - Nur E2E: `RUN_E2E=1 WEB_BASE=http://app.localhost:8100 KC_BASE=http://id.localhost:8100 .venv/bin/pytest -q -m e2e`

## Deployment & Betrieb
- Containerisiert über `Dockerfile` und `docker-compose.yml`.
- Reverse‑Proxy: Caddy (hostbasiertes Routing). Nur `127.0.0.1:8100` ist gemappt (lokal).
- Entwicklungsstart: `docker compose up --build` (Hot‑reload aktiv). Zugriff: `app.localhost:8100` und `id.localhost:8100`.
- Healthcheck: `GET /health` für einfache Verfügbarkeitsprüfung.

### Lokaler Betrieb & UFW
- Standard‑Empfehlung: Nur der Proxy (Caddy) published den Port; Services (web, keycloak) sind intern → UFW muss keine zusätzlichen Regeln erlauben.
- Optional LAN‑Betrieb: Port‑Bindung von Caddy auf `0.0.0.0:8100`; UFW‑Regel: `allow from <LAN‑CIDR> to any port 8100 proto tcp`.

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
