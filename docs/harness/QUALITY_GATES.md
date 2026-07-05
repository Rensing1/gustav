# Quality Gates

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; weitere Profile werden schrittweise ergänzt.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument beschreibt die geplanten Gate-Profile für den Harness-Refactor. Die Profile sollen lokale Entwicklung und CI angleichen, ohne teure oder externe Suites versehentlich in schnelle Checks zu mischen.

## Profile

### fast
Zweck: schnelles Feedback für die meisten Code- und Dokumentationsänderungen.

Geplanter Inhalt:
- In-Process-pytest ohne externe Dienste
- Domain- und Use-Case-Tests
- Adaptertests mit Fakes oder Mocks
- OpenAPI-/Contract-Tests, soweit sie keine laufenden Dienste brauchen
- Harness-Dokumentationsverträge

Initialer lokaler Befehl:
- `make test-fast`

### backend-lint
Zweck: einfache Python-Qualitätsprobleme früh sichtbar machen, ohne den Closeout-Refactor durch eine unbereinigte Altlastenflut zu blockieren.

Geplanter Inhalt:
- Ruff-Check für Pyflakes-Fehler im produktiven Backend-Code.
- Ruff-Format- und Importordnungs-Checks gegen die zentrale `pyproject.toml`, sobald die Alt-Baseline bereinigt ist.
- Keine automatische Massenformatierung zusammen mit fachlichen Refactors.
- Type-Checking wird separat bewertet und erst dann hart geschaltet, wenn eine realistische Baseline ohne große False-Positive-Last existiert.

Initialer lokaler Befehl:
- `make lint-backend`

Aktueller Status:
- `make lint-backend` ist als expliziter Target vorhanden.
- Das Profil prüft zunächst Pyflakes (`F`) für den gesamten Backend-Baum inklusive Tests und E2E-Tests.
- Das Profil ist bewusst nicht Teil von `make verify`, bis Ruff-Format, Importordnung, Tests und Type-Checking als realistische Baseline bereinigt sind.
- Wenn Closeout v1.1 ohne hartes Lint- oder Type-Gate abgeschlossen wird, muss der Restzustand in `docs/harness/TECH_DEBT.md` mit Owner, Review date, Risiko und Exit criterion dokumentiert werden.

### db-security
Zweck: Datenbank-, RLS-, Authz-, CSRF- und Migration-Sicherheit sichtbar machen.

Geplanter Inhalt:
- RLS-Tests gegen lokale Supabase-Struktur
- Migration- und Helper-Tests
- CSRF-positive und CSRF-negative Tests
- Authz-negative Tests für Schüler, Lehrer und Admin-Funktionen
- DB-DSN- und Mutationssicherheitsguards

Initialer lokaler Befehl:
- `make test-db-security`

Aktueller harter Inhalt:
- Config-, Privacy-, Test-Environment- und DB-required Guards.
- CSRF-Baseline für Learning-Submission- und Teaching-Write-Flows.
- Cookie-Policy-Baseline für Auth-Callback und BFF-Session-Sync.
- Authz/Authn-Baseline für unauthentifizierte API-Zugriffe, Bearer-JWT-Fehler, BFF-Session-Bootstrap und cookie-only Missbrauch.
- Fokussierte Teaching-Live-Detail-Node-IDs und Relation-Guard-Regressionen; breite Detail-, Feedback-, Datei- und H5P-Integrationen gehören nicht in dieses harte Authz/RLS-Gate.
- Learning- und Teaching-RLS-Regressionen inklusive Membership-Delete-Policies, SECURITY-DEFINER-Owner-Binding und Helper-EXECUTE-Privilegien.
- Das Profil setzt `REQUIRE_DB_TESTS=1`; fehlende lokale Supabase-DB oder fehlende App-Rollen führen zu einem Gate-Fehler statt zu stillen Skips.

Aktueller Inventarstatus:
- `make test-db-inventory` meldet 0 echte DB/RLS-Kandidaten ohne `db_read`/`db_write`.
- DB-Testinfrastruktur ist als `test-infra` klassifiziert und wird nicht als fehlender Marker gezählt.

### upload-llm-boundaries
Zweck: technische Upload-Grenzen und LLM-Datengrenzen sichtbar machen, ohne Schüler-Submissions inhaltlich vorzuprüfen oder umzuschreiben.

Geplanter Inhalt:
- Upload-Intent- und Proxy-Grenzen für Größe, MIME, erlaubte Hosts, Pfade und Header.
- Storage-Key-, Storage-Verifikations- und Content-Signatur-Contracts.
- Submission-Kind- und MIME-Casing-Contracts.
- Feedback-/DSPy-/Vision-Verträge, die Fehlerabbildung, Prompt-Struktur und Logging schützen.
- Privacy-Logging-Contracts.

Initialer lokaler Befehl:
- `make test-upload-llm-boundaries`

Aktueller harter Inhalt:
- Servicefreie Upload-, Storage-, Signatur-, Proxy-, Feedback- und Privacy-Tests.
- Die LLM-Produktentscheidung ist ein Harness-Contract: Schüler-Submissions werden vor dem LLM nicht inhaltlich geprüft, nicht gefiltert, nicht normalisiert, nicht moderiert und nicht umgeschrieben.
- Technische Verpackung ist erlaubt, solange das gespeicherte Original unverändert bleibt.

Bewusst opt-in:
- Supabase-Storage-, H5P-E2E- und OpenAI/Ollama-Smokes bleiben opt-in und werden nicht in dieses schnelle Boundary-Profil gemischt.

### docker-image-smoke
Zweck: Docker-Image-Parität sichtbar machen, damit Compose-Bind-Mounts fehlende Image-Inhalte nicht verdecken.

Geplanter Inhalt:
- Root-Web-Image bauen.
- Kritische Python-Imports im Image ohne Volume-Mounts prüfen.
- Container kurz starten und `/health` abfragen.
- Package-orientierten Start `backend.web.main:app` prüfen.

Initialer lokaler Befehl:
- `make test-docker-image-smoke`

Aktueller Status:
- Als hartes Gate in `make verify` enthalten.
- In `harness-signals` warning-only sichtbar.
- In CI als expliziter Schritt nach `make harness-minimum` sichtbar, damit Image-Parität nicht hinter Bind-Mounts verschwindet.
- Packaging-Contracts prüfen zusätzlich, dass Web und Learning-Worker das Backend lokal als ein Package unter `/app/backend` mounten und keine einzelnen Backend-Subpackages als zweite Wurzeln einhängen.

### import-boundaries
Zweck: Import-Schulden sichtbar machen und verhindern, dass flache Runtime-Imports oder verstreute Test-Import-Crutches weiter wachsen.

Geplanter Inhalt:
- Flat-Import-Baseline für `routes.*` und `components`.
- Mixed-Import-Baseline für `backend.web.routes.*` außerhalb des Web-Adapters.
- Baseline für verstreute `sys.path`-/`os.sys.path`-Manipulationen.
- Zielbild für `backend.web.main:app`, Dockerfile und Compose ohne doppelte Package-Kopien.

Initialer lokaler Befehl:
- `make test-import-boundaries`

Aktueller Status:
- Als hartes Baseline-Gate in `make verify` enthalten.
- In `harness-signals` warning-only sichtbar.
- In `harness-minimum` nur als schneller Scanner-Contract enthalten.

### api-contract-baseline
Zweck: `api/openapi.yml` als ausführbare Baseline für Runtime-`/api/*`-Routen schützen und Route-Surfaces sichtbar machen.

Geplanter Inhalt:
- Runtime-`/api/*`-Operationen der FastAPI-App gegen `api/openapi.yml` vergleichen.
- Stale `/api/*`-OpenAPI-Einträge als Gate-Fehler melden.
- Route-Surface-Klassifikation für public API, BFF/internal, H5P service, auth bridge, health/ops, active legacy UI und retired legacy UI prüfen.

Initialer lokaler Befehl:
- `make test-api-contract-baseline`

Aktueller Status:
- Als hartes Gate in `make verify` enthalten.
- In `harness-minimum` als schneller Contract enthalten.
- Der PR16-Contract prüft zusätzlich, dass die ersten entfernten Legacy-HTML/HTMX-Einstiegspfade nicht mehr als `APIRoute` registriert sind, während direkte Backend-Zugriffe weiterhin intentional 410 oder Rollen-Redirect liefern.

### architecture-boundaries
Zweck: ausgewählte Clean-Architecture-Grenzen mechanisch prüfen, ohne bestehende Altlasten zu verstecken.

Geplanter Inhalt:
- FastAPI-Imports in Use Cases und Services blockieren.
- Direkte DB-Zugriffe aus Web-Adaptern gegen eine Baseline zählen.
- Direkte Supabase-Client-Erzeugung aus Web-Adaptern gegen eine Baseline zählen.
- Zielbild für Security Guards und Serialisierung dokumentieren.

Initialer lokaler Befehl:
- `make test-architecture-boundaries`

Aktueller Status:
- Als hartes Gate in `make verify` enthalten.
- In `harness-minimum` als schneller Contract enthalten.

### route-map
Zweck: Route-Surfaces und Legacy-Status vor Monolith-Strangulation und Legacy-Removal reviewbar machen.

Geplanter Inhalt:
- Runtime- und OpenAPI-Operationen als Route-für-Route-Inventur in `docs/harness/ROUTE_MAP.md` führen.
- Pflichtfelder für Surface, Rolle, Datenzugriff, Response-Modell, Tests, Risiko, Legacy-Status, Entscheidung und Zielschicht prüfen.
- Bereits registrierte 410-Legacy-Routen von aktiver Legacy-UI unterscheiden.

Initialer lokaler Befehl:
- `make test-route-map`

Aktueller Status:
- Als hartes Gate in `make verify` enthalten.
- In `harness-minimum` als schneller Contract enthalten.

### frontend-h5p
Zweck: Frontend- und H5P-Qualität als First-Class-Gate behandeln.

Geplanter Inhalt:
- `npm run check` im Frontend
- Vitest im Frontend
- Node-Tests im H5P-Service
- H5P-Verträge, soweit sie ohne Compose laufen

Initialer lokaler Befehl:
- `make test-frontend-h5p`

Aktueller harter Inhalt:
- `npm run check` im Frontend.
- Frontend-Vitest.
- H5P-Node-Tests.
- `make verify` ruft dieses Profil auf.

Bewusst opt-in:
- Browser-E2E und visuelle Regressionen bleiben im `full-prod-like`-Profil.

### full-prod-like
Zweck: produktionsnahe Integrationen prüfen.

Geplanter Inhalt:
- Supabase-Integration
- OpenAI-kompatibler Endpoint-Smoke
- Docker/Compose-Smoke
- Keycloak/Caddy/Web/H5P-E2E
- wenige Playwright- oder pytest-E2E-Kernreisen

Initialer lokaler Befehl:
- `make test-full-prod-like`

Regel:
- Dieses Profil bleibt teuer und bewusst opt-in oder CI-staged.

### db-inventory
Zweck: DB-, RLS-, Migrations- und Supabase-nahe Testdateien sichtbar machen, bevor `db_read` und `db_write` harte Marker werden.

Lokaler Befehl:
- `make test-db-inventory`

Aktueller Status:
- Implementiert als generierter Synchronitätscheck (`backend/tools/db_test_inventory.py`) mit Markdown-Bericht in `docs/harness/DB_TEST_INVENTORY.md`.
- `make verify` prüft, dass das Inventar aktuell ist.
- `missing-db-marker` ist ein Fehlerzustand: echte DB/RLS-Kandidaten ohne `db_read`/`db_write` dürfen nicht in der Baseline verbleiben.

### quality-scorecard
Zweck: den Refactor-Status monatlich messbar machen.

Geplanter Inhalt:
- Hotspot-LOC je definierter Backend-/Frontend-/H5P-Datei.
- Security-Check-Status.
- OpenAPI-/Route-Map-Contract-Diff-Status.
- Offene TECH_DEBT-Einträge.
- Skill-Inventory und Evaluationsstatus.
- Docker-Image-Paritätsnachweis.

Initialer lokaler Befehl:
- `make quality-scorecard`

Aktueller Status:
- Implementiert als eigenständiger Reporter (`backend/tools/quality_scorecard.py`) mit:
  - Markdown-Bericht in `docs/harness/QUALITY_SCORECARD.md`
  - JSON-Historie in `docs/harness/QUALITY_SCORECARD_HISTORY.json`
- Sicherheits-, Contract- und Docker-Image-Paritätschecks laufen im Standardmodus, damit der Monatsbericht keine unausgeführten Docker-Prüfungen ausweist.

## Harte Regeln
- Sicherheits-, Privacy-, Secret- und API-Security-Contract-Fehler blockieren sofort.
- Struktur-, Hotspot-, Route-Surface-, Import- und Skill-Governance-Signale dürfen anfangs Warnungen sein, müssen aber einen Härtungstermin haben.
- Grüne harte Gates sollen warning-clean sein. Wenn ein grüner Lauf eine Warnung ausgibt, wird sie als aufzuräumende technische Schuld behandelt oder mit Owner und Härtungspfad dokumentiert.
- Externe Suites brauchen explizite Marker und ENV-Flags.
- Kein Gate darf lokale Sonderpfade nutzen, die in Produktion nicht gelten.

## Pflege
- Neue Gates beginnen als Contract-Test oder fokussierter Make-Target und werden erst dokumentiert, wenn der lokale Befehl existiert.
- Baselines dürfen nur mit Begründung gesenkt oder verschärft werden; Wachstum in Import-, Architektur-, Route- oder DB-Inventaren ist ein Gate-Fehler.
- Externe Integrationssuites bleiben bewusst opt-in und brauchen explizite Marker und ENV-Flags.
