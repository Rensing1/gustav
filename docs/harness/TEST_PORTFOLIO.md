# Testportfolio

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: Keine anbietergebundene CI erforderlich; `make verify` führt Import-, Architektur-, Route-, DB-, Docker-, Backend-, Frontend- und H5P-Gates lokal hart aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument macht das Testportfolio steuerbar. Es ist bewusst ein Gruppeninventar, keine vollständige Liste jeder Testfunktion; die maschinenlesbaren Detailinventare liegen in den spezialisierten Harness-Artefakten wie Route Map, Import-Baseline und DB-Test-Inventar.

## Entscheidungswerte
- `keep`: behalten, weil Zweck und Ebene passen.
- `merge`: mit ähnlichen Tests zusammenführen.
- `rewrite`: auf eine passendere Ebene verschieben oder vereinfachen.
- `retire-later`: nicht mehr als strategischer Schutz betrachten, aber erst nach bewusster Entscheidung entfernen.

## Portfolio-Baseline

| Bereich | Beispielpfade | Zweck | Ebene | Abhängigkeiten | Marker | Gate | Risiko | Entscheidung |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAPI und Contract | `backend/tests/test_openapi_*.py`, `backend/tests/*contract*.py`, `backend/tools/openapi_contract_check.py` | Öffentliche API, Runtime-`/api/*`-Parität und dokumentierte Shapes schützen | OpenAPI/API-Contract | keine externen Dienste | meist keiner | `test-api-contract-baseline`, `fast`, `verify` | viele Einzeltests können redundant oder zu spezifisch sein | keep |
| Route Map und Legacy-Surface | `backend/tests/test_route_map_inventory_contract.py`, `backend/tests/test_legacy_html_exit_wave1_contract.py`, `backend/tools/route_map_inventory.py`, `docs/harness/ROUTE_MAP.md` | Route-für-Route-Inventur, Legacy-Status, Risiko, Zielschicht und bewusst entfernte Legacy-Einstiegspfade sichtbar machen | Architektur-Contract, Route-Surface | keine externen Dienste | keiner | `route-map`, `harness-minimum`, `verify` | Heuristiken ersetzen keine fachliche Removal-Entscheidung; H5P-Sidecar-Runtime wird durch H5P-Node-Tests und opt-in E2E-Smokes separat geprüft | keep |
| Backend Use Cases und API | `backend/tests/test_learning_*`, `backend/tests/test_teaching_*` | Fachliche Regeln und HTTP-Verhalten schützen | Domain, API-Integration | teilweise lokale DB | uneinheitlich | `fast`, teils `db-security` | HTTP kann reine Logik übertesten | keep, Ebene pro Gruppe prüfen |
| Security und Auth | `backend/tests/test_auth_*`, `backend/tests/test_*csrf*`, `backend/tests/test_*rls*`, `backend/tests/test_privacy_*` | AuthN/AuthZ, CSRF, RLS, Cookies, Privacy und Secrets schützen | Security, DB/RLS, API-Integration | teilweise lokale DB | `db_read`/`db_write` für echte DB/RLS-Kandidaten | `db-security`, `db-inventory`, `verify` | fehlende negative Fälle wären kritisch | keep |
| DB und Migration | `backend/tests/migration/*`, `backend/tests/test_db_*` | Migrationen, Grants, Constraints, Helper und sichere DSNs prüfen | DB/RLS/Migration | lokale Supabase-DB | `legacy_migration` teilweise | `db-security` oder opt-in | globale Mutationen und Legacy-Altlasten | keep für aktive DB-Sicherheit, retire-later für Legacy |
| AI, Worker und Adapter | `backend/tests/learning_adapters/*`, `backend/tests/test_learning_worker_*` | DSPy, Vision, Feedback, Worker und Fehlerabbildung schützen | Adapter, Domain, Integration | Mocks, optionale Dienste | `openai_integration` für echte Smoke-Tests | `upload-llm-boundaries`, `fast`, opt-in | Modell-/Provider-Verhalten kann Tests fragil machen; Schüler-Submissions dürfen nicht heimlich vorverändert werden | keep, echte Modelltests klein halten |
| Storage und Uploads | `backend/tests/test_supabase_storage_*`, `backend/tests/test_learning_upload_*`, `backend/tests/storage/*` | Upload, Presign, Finalize, Download, MIME, Size und Pfade schützen | Adapter, API, Supabase-Integration | teils Supabase | `supabase_integration` für echte Storage-Flows | `upload-llm-boundaries`, `fast`, opt-in | Security-relevant; darf nicht nur happy path sein | keep |
| Docker und Packaging | `backend/tests/test_docker_image_smoke_contract.py`, `backend/tests/packaging/*`, `backend/tests/test_learning_worker_packaging_contract.py` | Image-Inhalte, Importpfade, Build-Hygiene und Compose-Routing sichtbar machen | Packaging, Contract, Smoke | Docker für echten Smoke | keiner | `docker-image-smoke`, `harness-signals` | Bind-Mounts können fehlende Image-Inhalte verdecken | keep |
| Import- und Architekturgrenzen | `backend/tests/test_import_boundary_gate_contract.py`, `backend/tests/test_architecture_boundary_gate_contract.py`, `backend/tools/import_boundary_scan.py`, `backend/tools/architecture_boundary_scan.py`, `docs/harness/IMPORT_BOUNDARY_BASELINE.json`, `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json` | Flache Imports, gemischte Web-Imports, verstreute `sys.path`-Manipulationen, FastAPI-Use-Case-Leaks und Web-DB-Direktzugriffe zählen und neues Wachstum blockieren | Packaging, Architektur-Contract | keine externen Dienste | keiner | `import-boundaries`, `architecture-boundaries`, `verify`, `harness-signals` | Baseline-Wachstum ist ein Gate-Fehler; bestehende Architektur-Ausnahmen bleiben explizit gezählt | keep |
| H5P Backend und Sidecar | `backend/tests/test_h5p_*`, `h5p-service/test/*.test.mjs` | H5P-Routen, Assets, Auth, Cookies und Sidecar-Verträge schützen | Contract, Adapter, H5P-Service | Node, teils Compose | teils `e2e` | `frontend-h5p`, `full-prod-like` | eigene Runtime kann durch Backend-only-Tests übersehen werden | keep |
| Frontend Vitest und SvelteKit | `frontend/src/**/*.test.ts` | Komponenten, Route-Contracts, BFF-Proxy und UI-Zustände schützen | Frontend | Node/jsdom | keiner | `frontend-h5p`, `verify` | Browser-E2E und visuelle Regressionen sind weiterhin separat | keep |
| Browser E2E | `backend/tests_e2e/*`, `frontend/e2e/*` | Produktnahe Kernreisen über mehrere Dienste prüfen | E2E-Smoke | Docker Compose, Keycloak, Caddy, H5P | `e2e` | `full-prod-like` | teuer und fragil; nicht für Detailabdeckung | keep, Anzahl bewusst klein halten |
| Legacy Migration | `backend/tests/migration/test_legacy_*` | Alpha1-Importwissen und Migrationspfade erhalten | Legacy/Migration | teils DB, teils Dateien | `legacy_migration` | opt-in | kann Standardverify verlangsamen oder riskant mutieren | retire-later prüfen |

## Pflegefragen
- Welche OpenAPI-Einzeltests können durch generische Contract-Gates ersetzt werden?
- Welche Backend-API-Tests prüfen eigentlich reine Use-Case-Logik und sollten tiefer wandern?
- Welche Security-Flows haben keinen negativen Test?
- Welche DB-Tests nutzen echte RLS-Pfade und welche prüfen nur API-Filter?
- Welche Legacy-Tests schützen noch produktives Risiko und welche sind Archivwissen?

## v1.4 Testdatei-Entscheidungen

| Datei | LOC | Entscheidung | Begründung |
| --- | ---: | --- | --- |
| `backend/tests/test_learning_api_contract.py` | 2326 | rewrite/split | API-, DB- und Authz-Grenzen bleiben wichtig; die Datei soll nach Learning-Submissions, Upload/Finalize, Material/History und H5P Access geteilt werden. |
| `backend/tests/test_learning_worker_jobs.py` | 2009 | rewrite/split | Worker-Semantik ist kritisch; Queue, Transaction Boundaries, Error Mapping und Privacy Logs sollen getrennte Testflächen werden. |
| `backend/tests/test_teaching_live_unit_summary_api.py` | 1219 | rewrite/split | Summary-/Delta-/Owner-Grenzen bleiben tabu, aber die Datei ist zu breit für gezielte Live-Refactors. |
| `backend/tests/test_teaching_live_detail_api.py` | 1184 | rewrite/split | Detail-, Relation-Guard- und H5P-Review-Credential-Verhalten sollen klarer getrennt werden. |
| `backend/tests/test_gustav_cli.py` | 1210 | rewrite/split | CLI-Sicherheitsregeln bleiben wichtig; Auth, Units/Sections, Materials/Tasks, H5P und Config-Schutz sollen getrennt werden. |
| `frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts` | 1202 | rewrite/split | Drafts, Review/History, Upload-Artefakte, H5P und Style-Contracts sollen getrennte Komponenten-/Contract-Tests werden. |
| `backend/tests/migration/test_import_snapshot_backup.py` | 1094 | retire-later | Alpha1-/Snapshot-Wissen bleibt erhalten, bis der Legacy-Import als aktiver Produktpfad bewusst beendet ist. |
| `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py` | 924 | merge | Vision-/DSPy-Fakes sollen mit verwandten Adaptertests geteilt werden; keine Abdeckung für Schüler-Submission-Integrität verlieren. |

## Tabu ohne Ersatz-Contract

Diese Gruppen werden nicht zusammengelegt, gekürzt oder retired, solange kein gleichwertiger Ersatz-Contract existiert:
- Security/Auth: `backend/tests/test_auth_*`, `test_csrf_tokens_contract.py`, `test_bearer_jwt_auth_api.py`, `test_bff_authorization_session_api.py`, `test_session_bootstrap_api.py`.
- DB/RLS/Migration: `backend/tests/test_learning_student_rls_policies.py`, `test_learning_rls_owners.py`, `test_teaching_rls_policies_optional.py`, `backend/tests/migration/test_*rls*`, `test_db_test_inventory_contract.py`.
- API/OpenAPI/Architektur: `test_openapi_*`, `test_openapi_route_surface_baseline.py`, `test_import_boundary_gate_contract.py`, `test_architecture_boundary_gate_contract.py`, `test_route_map_inventory_contract.py`.
- Upload/Storage/Privacy: `test_learning_internal_proxy_security.py`, `test_storage_verification_streaming_security.py`, `test_upload_llm_boundaries_contract.py`, `test_privacy_logging_contract.py`.
- H5P-Sidecar-Security: `h5p-service/test/auth_forwarding.test.mjs`, `cookies.test.mjs`, `internal_auth.test.mjs`, `runtime_guards.test.mjs`, `security_headers.test.mjs`, `review_tokens.test.mjs`.
- Frontend Auth/BFF: `frontend/src/lib/server/backend-auth.test.ts`, `bff-proxy.test.ts`, `session.test.ts`.

## Aktueller Befund
- Das Repo hat bereits viele Tests und einige sinnvolle Opt-in-Guards.
- DB/RLS-Kandidaten sind im generierten DB-Test-Inventar markiert oder als `test-infra` beziehungsweise opt-in klassifiziert.
- Frontend- und H5P-Tests sind über `make test-frontend-h5p` Bestandteil von `make verify`.
- Spezialinventare ersetzen ein monolithisches Gesamt-Testinventar: OpenAPI, Route Map, Import-Baseline, Architektur-Baseline, DB-Test-Inventar und Scorecard sind die aktuellen maschinenlesbaren Prüfquellen.
