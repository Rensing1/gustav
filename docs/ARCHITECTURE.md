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
- Datenbank: PostgreSQL via Supabase; Migrationen unter `supabase/migrations/` verwaltet. RLS aktiviert;
  der Teaching‑Kontext nutzt standardmäßig eine Limited‑Role‑DSN (`gustav_limited`).
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

Im Code spiegeln sich diese Kontexte perspektivisch als Pakete unter `backend/` wider. Startpunkt ist aktuell der Web-Adapter; die Extraktion der Use Cases folgt, sobald erste API-Funktionen entstehen.

### Teaching: Aufgaben (Tasks) MVP
- API: `GET|POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks`, `PATCH|DELETE /tasks/{task_id}`, `POST /tasks/reorder` (authorOnly, Teacher-role).
- Vertrag: `Task` Schema besitzt `kind` (read-only, default `native`) für spätere H5P-Erweiterungen.
- Use Case Layer: `teaching.services.tasks.TasksService` normalisiert Eingaben (Criteria, Hints, Due-Date, Max-Attempts) und delegiert an das Repo (`TasksRepoProtocol`).
- Persistenz: Supabase-Migration legt `public.unit_tasks` mit RLS, Triggern für Positionsresequenzierung und DEFERRABLE Unique-Constraint an.
- Tests: API-Integrationstests spiegeln die BDD-Szenarien (CRUD, Reorder, Fehlerfälle); dedizierte Unit-Tests prüfen den Service isoliert.
 - Validierung & Semantik:
   - Pfadparameter werden früh validiert; ungültige UUIDs führen zu `400 bad_request` mit `invalid_unit_id`, `invalid_section_id` oder `invalid_task_id`.
   - `criteria`-Einträge müssen nicht-leere Strings sein (`minLength: 1`).
   - `due_at` akzeptiert ISO-8601 mit Zeitzone, inkl. `Z` (UTC), und wird zu `+00:00` normalisiert.
   - DELETE-Endpunkte liefern `204 No Content` ohne Body.

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
  - Persistenz (DEV): `keycloak_data:/opt/keycloak/data` Volume hält Realm‑ und Benutzer‑Daten über Rebuilds.
    Für PROD sollte Keycloak an eine externe DB (KC_DB=postgres) angebunden werden.
  - Vorteil: keine Pfadpräfixe/Rewrite‑Komplexität, korrekte Hostname‑Links, klare Trennung.
  - Setup: `/etc/hosts` → `127.0.0.1 app.localhost id.localhost`.
- PROD (Security‑first, geringe App‑Komplexität):
  - `/auth/login|register|forgot` leiten zur gebrandeten Keycloak‑UI (Authorization‑Code‑Flow mit PKCE).
  - GUSTAV verarbeitet keine Passwörter; Sessions sind serverseitig und über `gustav_session` gesichert.

#### Keycloak Theme (GUSTAV)
- Pfad: `keycloak/themes/gustav/login`
  - Templates: `templates/login.ftl`, `templates/register.ftl`, `templates/login-reset-password.ftl`
  - Styles: `resources/css/gustav.css` (kompaktes Layout über .kc‑* Klassen)
  - Gemeinsames Basis‑CSS: Das kanonische App‑CSS `backend/web/static/css/gustav.css` wird beim Keycloak‑Image‑Build als `resources/css/app-gustav-base.css` in das Theme kopiert. So teilen sich IdP‑UI und App dieselbe Styles‑Quelle – ohne Runtime‑Volumes.
  - i18n: `messages/messages_de.properties` (DE‑Texte)
- Realm‑Konfiguration: `keycloak/realm-gustav.json:1`
  - `loginTheme: "gustav"`, `internationalizationEnabled: true`, `defaultLocale: "de"`, `supportedLocales: ["de","en"]`

#### Vereinheitlichter Flow
- Direct‑Grant und SSR‑Formulare wurden entfernt. Sowohl in DEV als auch PROD leiten `/auth/login|register|forgot` zur Keycloak‑UI (Authorization‑Code‑Flow mit PKCE).

#### Ablauf Authorization‑Code‑Flow
1) Browser: `GET /auth/login` (GUSTAV) → 302 zu IdP `…/protocol/openid-connect/auth` (Host: `id.localhost`).
2) Login auf IdP‑UI (gebrandet). `GET /auth/register` nutzt ebenfalls den Auth‑Endpoint und setzt `kc_action=register` (statt altem `…/registrations`‑Pfad), optional mit `login_hint`.
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
- Registrierung – Validierungen/Fehlerfälle: `backend/tests_e2e/test_identity_register_validation_e2e.py`
- Voraussetzung: `docker compose up -d caddy web keycloak` und Hosts‑Eintrag `127.0.0.1 app.localhost id.localhost`.
- Ausführung:
  - Alle Tests inkl. E2E: `.venv/bin/pytest -q`
  - Nur E2E: `RUN_E2E=1 WEB_BASE=http://app.localhost:8100 KC_BASE_URL=http://id.localhost:8100 .venv/bin/pytest -q -m e2e`

### Auth Router & Security (aktualisiert)
- Routenorganisation: Auth‑Endpunkte liegen im Router `backend/web/routes/auth.py` und werden in `backend/web/main.py` eingebunden. Die Slim‑App in Tests nutzt denselben Router, um Drift zu vermeiden.
- `/api/me`: Antworten enthalten `Cache-Control: no-store` zur Verhinderung von Caching von Auth‑Zuständen.
- Vereinheitlichter Logout: `GET /auth/logout` löscht die App‑Session (Cookie) und leitet zur End‑Session beim IdP; danach Rückkehr zur Erfolgsseite (`/auth/logout/success`). Optional ist ein interner absoluter Redirect‑Pfad erlaubt; unsichere oder zu lange Werte werden ignoriert.

#### Auth‑Erzwingung (Middleware)
- Allowlist: `/auth/*`, `/health`, `/static/*`, `/favicon.ico` werden nie umgeleitet.
- HTML‑Anfragen ohne Session: `302` Redirect zu `/auth/login`.
- JSON‑/API‑Anfragen ohne Session (Pfad beginnt mit `/api/`): `401` JSON mit `Cache-Control: no-store`.
- HTMX‑Requests ohne Session: `401` mit Header `HX-Redirect: /auth/login`.
- Bei erfolgreicher Authentifizierung setzt die Middleware `request.state.user = { sub, name, role, roles }` für SSR; die primäre Rolle wird deterministisch nach Priorität gewählt (admin > teacher > student).

#### Sicherheits‑Härtung (Auth)
- `/auth/callback` liefert bei allen Fehlern `400` mit `Cache-Control: no-store` (nicht cachebar).
- `/auth/login` ignoriert einen client‑übergebenen `state` vollständig; `state` wird ausschließlich serverseitig erzeugt und validiert (CSRF‑Schutz).
- Redirect‑Parameter sind nur als interne absolute Pfade erlaubt. Server‑seitig erzwungenes Pattern (spiegelt OpenAPI): `^(?!.*//)(?!.*\\.\\.)/[A-Za-z0-9._\-/]*$`, `maxLength: 256`. Doppelte Slashes (`//`) und Pfadtraversalen (`..`) sind nicht erlaubt. Ungültige Werte werden ignoriert (Login → `/`, Logout → `/auth/logout/success`).
- `/auth/logout` verwendet, falls verfügbar, `id_token_hint` für bessere IdP‑Kompatibilität; andernfalls `client_id`.

#### CSRF‑Strategie (Browser‑Flows)
- Same‑Site Cookies: In PROD `SameSite=strict` + `Secure`; in DEV `lax`.
- Server prüft bei schreibenden Learning‑APIs (`POST /submissions`) die **Origin**.
  Fehlt `Origin`, wird als Fallback die **Referer**‑Origin herangezogen.
- Um diesen Fallback zu unterstützen und dennoch keine sensiblen Daten zu leaken,
  wird global `Referrer-Policy: strict-origin-when-cross-origin` gesetzt.

#### Redirect‑URI‑Sicherheit
- `redirect_uri` wird dynamisch nur dann auf den Request‑Host gesetzt, wenn
  dieser Host gegen `WEB_BASE` (oder die konfigurierte `OIDC_CFG.redirect_uri`)
  übereinstimmt. Bei Mismatch wird die statische `redirect_uri` verwendet.

#### Nonce & Session‑TTL
- Nonce: Beim Start des Login‑Flows generiert die App zusätzlich zum `state` eine OIDC‑`nonce`. Diese wird in der Authorization‑URL mitgegeben und beim Callback gegen das `nonce`‑Claim des ID‑Tokens geprüft. Mismatch → `400` + `Cache-Control: no-store`.
- Session‑TTL & Cookie: Serverseitige Sessions besitzen eine TTL (Standard 3600 s). In PROD wird das `gustav_session`‑Cookie mit `Max-Age=<TTL>` gesetzt; Flags: `HttpOnly; Secure; SameSite=strict`. In DEV wird kein `Max-Age` gesetzt (`SameSite=lax`).
- /api/me: liefert zusätzlich `expires_at` (UTC‑ISO‑8601), damit Clients die Restlaufzeit anzeigen können. Antworten sind nie cachebar.

## Deployment & Betrieb
- Containerisiert über `Dockerfile` und `docker-compose.yml`.
- Reverse‑Proxy: Caddy (hostbasiertes Routing). Nur `127.0.0.1:8100` ist gemappt (lokal).
- Entwicklungsstart: `docker compose up --build` (Hot‑reload aktiv). Zugriff: `app.localhost:8100` und `id.localhost:8100`.
- Healthcheck: `GET /health` für einfache Verfügbarkeitsprüfung; Antworten sind nicht cachebar
  (`Cache-Control: no-store`).

### Storage (Supabase)
- Self‑hosted via Supabase CLI. Storage ist privat; Zugriff ausschließlich über kurzlebige signierte URLs.
- Bucket: `materials` (lokal in `supabase/config.toml` konfiguriert; 20 MiB; PDF/PNG/JPEG).
- Adapter: `backend/teaching/storage_supabase.py` implementiert Zugriff (presign upload/download, head, delete).
- Wiring: In `backend/web/main.py` wird der Adapter automatisch aktiviert, wenn `SUPABASE_URL` und `SUPABASE_SERVICE_ROLE_KEY` gesetzt sind.
- ENV: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `SUPABASE_STORAGE_BUCKET` (default: `materials`). Siehe `.env.example` und `docs/references/storage_and_gateway.md`.

### RLS & Ordering (Teaching/Sections)
- RLS‑Identität: Jede DB‑Operation setzt `SET LOCAL app.current_sub = '<sub>'` (psycopg), sodass Policies die Aufrufer‑Identität kennen.
- Limited‑Role‑DSN: Runtime verwendet ausschließlich die `gustav_limited`‑Rolle. Service‑/Owner‑Rollen sind Migrationen vorbehalten.
- Author‑Scope: `unit_sections` ist über `units.author_id = app.current_sub` abgesichert (SELECT/INSERT/UPDATE/DELETE).
- Atomare Reorder: Unique `(unit_id, position)` ist DEFERRABLE; Reorder setzt `SET CONSTRAINTS … DEFERRED` und updated alle Positionen in einer Transaktion.
- Concurrency: Neue `position` wird mit Row‑Lock auf die Unit‑Sections ermittelt, um doppelte Positionen zu vermeiden.

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
