# Testportfolio

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`; weitere Profile werden schrittweise ergänzt.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument macht das Testportfolio steuerbar. Es ist bewusst ein Gruppeninventar, keine vollständige Liste jeder Testfunktion. Die Detailzählung wird in einer späteren Baseline ergänzt.

## Entscheidungswerte
- `keep`: behalten, weil Zweck und Ebene passen.
- `merge`: mit ähnlichen Tests zusammenführen.
- `rewrite`: auf eine passendere Ebene verschieben oder vereinfachen.
- `retire-later`: nicht mehr als strategischer Schutz betrachten, aber erst nach bewusster Entscheidung entfernen.

## Portfolio-Baseline

| Bereich | Beispielpfade | Zweck | Ebene | Abhängigkeiten | Marker | Gate | Risiko | Entscheidung |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAPI und Contract | `backend/tests/test_openapi_*.py`, `backend/tests/*contract*.py`, `backend/tools/openapi_contract_check.py` | Öffentliche API, Runtime-`/api/*`-Parität und dokumentierte Shapes schützen | OpenAPI/API-Contract | keine externen Dienste | meist keiner | `test-api-contract-baseline`, `fast`, `verify` | viele Einzeltests können redundant oder zu spezifisch sein | keep, später merge prüfen |
| Route Map und Legacy-Surface | `backend/tests/test_route_map_inventory_contract.py`, `backend/tests/test_legacy_html_exit_wave1_contract.py`, `backend/tools/route_map_inventory.py`, `docs/harness/ROUTE_MAP.md` | Route-für-Route-Inventur, Legacy-Status, Risiko, Zielschicht und bewusst entfernte Legacy-Einstiegspfade sichtbar machen | Architektur-Contract, Route-Surface | keine externen Dienste | keiner | `route-map`, `harness-minimum`, `verify` | Heuristiken ersetzen keine fachliche Removal-Entscheidung; H5P-Sidecar-Runtime wird später separat geprüft | keep |
| Backend Use Cases und API | `backend/tests/test_learning_*`, `backend/tests/test_teaching_*` | Fachliche Regeln und HTTP-Verhalten schützen | Domain, API-Integration | teilweise lokale DB | uneinheitlich | `fast`, teils `db-security` | HTTP kann reine Logik übertesten | keep, Ebene pro Gruppe prüfen |
| Security und Auth | `backend/tests/test_auth_*`, `backend/tests/test_*csrf*`, `backend/tests/test_*rls*`, `backend/tests/test_privacy_*` | AuthN/AuthZ, CSRF, RLS, Cookies, Privacy und Secrets schützen | Security, DB/RLS, API-Integration | teilweise lokale DB | uneinheitlich | `db-security` | fehlende negative Fälle wären kritisch | keep, Marker schärfen |
| DB und Migration | `backend/tests/migration/*`, `backend/tests/test_db_*` | Migrationen, Grants, Constraints, Helper und sichere DSNs prüfen | DB/RLS/Migration | lokale Supabase-DB | `legacy_migration` teilweise | `db-security` oder opt-in | globale Mutationen und Legacy-Altlasten | keep für aktive DB-Sicherheit, retire-later für Legacy |
| AI, Worker und Adapter | `backend/tests/learning_adapters/*`, `backend/tests/test_learning_worker_*` | DSPy, Vision, Feedback, Worker und Fehlerabbildung schützen | Adapter, Domain, Integration | Mocks, optionale Dienste | `openai_integration` für echte Smoke-Tests | `upload-llm-boundaries`, `fast`, opt-in | Modell-/Provider-Verhalten kann Tests fragil machen; Schüler-Submissions dürfen nicht heimlich vorverändert werden | keep, echte Modelltests klein halten |
| Storage und Uploads | `backend/tests/test_supabase_storage_*`, `backend/tests/test_learning_upload_*`, `backend/tests/storage/*` | Upload, Presign, Finalize, Download, MIME, Size und Pfade schützen | Adapter, API, Supabase-Integration | teils Supabase | `supabase_integration` für echte Storage-Flows | `upload-llm-boundaries`, `fast`, opt-in | Security-relevant; darf nicht nur happy path sein | keep |
| Docker und Packaging | `backend/tests/test_docker_image_smoke_contract.py`, `backend/tests/packaging/*`, `backend/tests/test_learning_worker_packaging_contract.py` | Image-Inhalte, Importpfade, Build-Hygiene und Compose-Routing sichtbar machen | Packaging, Contract, Smoke | Docker für echten Smoke | keiner | `docker-image-smoke`, `harness-signals` | Bind-Mounts können fehlende Image-Inhalte verdecken | keep |
| Import- und Architekturgrenzen | `backend/tests/test_import_boundary_gate_contract.py`, `backend/tests/test_architecture_boundary_gate_contract.py`, `backend/tools/import_boundary_scan.py`, `backend/tools/architecture_boundary_scan.py`, `docs/harness/IMPORT_BOUNDARY_BASELINE.json`, `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json` | Flache Imports, gemischte Web-Imports, verstreute `sys.path`-Manipulationen, FastAPI-Use-Case-Leaks und Web-DB-Direktzugriffe zählen und neues Wachstum blockieren | Packaging, Architektur-Contract | keine externen Dienste | keiner | `import-boundaries`, `architecture-boundaries`, `verify`, `harness-signals` | Scanner reduzieren bestehende Schuld nicht automatisch; PR 8/9/12 müssen Baselines senken oder erklären | keep |
| H5P Backend und Sidecar | `backend/tests/test_h5p_*`, `h5p-service/test/*.test.mjs` | H5P-Routen, Assets, Auth, Cookies und Sidecar-Verträge schützen | Contract, Adapter, H5P-Service | Node, teils Compose | teils `e2e` | `frontend-h5p`, `full-prod-like` | eigene Runtime kann durch Backend-only-Tests übersehen werden | keep |
| Frontend Vitest und SvelteKit | `frontend/src/**/*.test.ts` | Komponenten, Route-Contracts, BFF-Proxy und UI-Zustände schützen | Frontend | Node/jsdom | keiner | `frontend-h5p`, `verify` | Browser-E2E und visuelle Regressionen sind weiterhin separat | keep |
| Browser E2E | `backend/tests_e2e/*`, `frontend/e2e/*` | Produktnahe Kernreisen über mehrere Dienste prüfen | E2E-Smoke | Docker Compose, Keycloak, Caddy, H5P | `e2e` | `full-prod-like` | teuer und fragil; nicht für Detailabdeckung | keep, Anzahl bewusst klein halten |
| Legacy Migration | `backend/tests/migration/test_legacy_*` | Alpha1-Importwissen und Migrationspfade erhalten | Legacy/Migration | teils DB, teils Dateien | `legacy_migration` | opt-in | kann Standardverify verlangsamen oder riskant mutieren | retire-later prüfen |

## Nächste Audit-Fragen
- Welche OpenAPI-Einzeltests können durch generische Contract-Gates ersetzt werden?
- Welche Backend-API-Tests prüfen eigentlich reine Use-Case-Logik und sollten tiefer wandern?
- Welche Security-Flows haben keinen negativen Test?
- Welche DB-Tests nutzen echte RLS-Pfade und welche prüfen nur API-Filter?
- Welche Frontend-Tests gehören in `make verify`, bevor Backend-Refactors API-Shapes ändern?
- Welche Legacy-Tests schützen noch produktives Risiko und welche sind Archivwissen?

## Aktueller Befund
- Das Repo hat bereits viele Tests und einige sinnvolle Opt-in-Guards.
- Die Marker-Strategie ist noch nicht konsequent genug sichtbar.
- Frontend- und H5P-Tests existieren, sind aber im Refactor-Plan noch nicht früh genug als harte Portfolio-Bestandteile verankert.
- Die nächste Änderung sollte ein maschinenlesbares oder halbautomatisches Testinventar erzeugen, bevor Tests zusammengeführt oder entfernt werden.
