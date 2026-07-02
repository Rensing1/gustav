# Testportfolio

Status: Draft
Owner: Felix
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_test_strategy_docs_contract.py`
CI status: geplant
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
| OpenAPI und Contract | `backend/tests/test_openapi_*.py`, `backend/tests/*contract*.py` | Öffentliche API und dokumentierte Shapes schützen | OpenAPI/API-Contract | keine externen Dienste | meist keiner | `fast` | viele Einzeltests können redundant oder zu spezifisch sein | keep, später merge prüfen |
| Backend Use Cases und API | `backend/tests/test_learning_*`, `backend/tests/test_teaching_*` | Fachliche Regeln und HTTP-Verhalten schützen | Domain, API-Integration | teilweise lokale DB | uneinheitlich | `fast`, teils `db-security` | HTTP kann reine Logik übertesten | keep, Ebene pro Gruppe prüfen |
| Security und Auth | `backend/tests/test_auth_*`, `backend/tests/test_*csrf*`, `backend/tests/test_*rls*`, `backend/tests/test_privacy_*` | AuthN/AuthZ, CSRF, RLS, Cookies, Privacy und Secrets schützen | Security, DB/RLS, API-Integration | teilweise lokale DB | uneinheitlich | `db-security` | fehlende negative Fälle wären kritisch | keep, Marker schärfen |
| DB und Migration | `backend/tests/migration/*`, `backend/tests/test_db_*` | Migrationen, Grants, Constraints, Helper und sichere DSNs prüfen | DB/RLS/Migration | lokale Supabase-DB | `legacy_migration` teilweise | `db-security` oder opt-in | globale Mutationen und Legacy-Altlasten | keep für aktive DB-Sicherheit, retire-later für Legacy |
| AI, Worker und Adapter | `backend/tests/learning_adapters/*`, `backend/tests/test_learning_worker_*` | DSPy, Vision, Feedback, Worker und Fehlerabbildung schützen | Adapter, Domain, Integration | Mocks, optionale Dienste | `openai_integration` für echte Smoke-Tests | `fast`, opt-in | Modell-/Provider-Verhalten kann Tests fragil machen | keep, echte Modelltests klein halten |
| Storage und Uploads | `backend/tests/test_supabase_storage_*`, `backend/tests/test_learning_upload_*`, `backend/tests/storage/*` | Upload, Presign, Finalize, Download, MIME, Size und Pfade schützen | Adapter, API, Supabase-Integration | teils Supabase | `supabase_integration` für echte Storage-Flows | `fast`, opt-in | Security-relevant; darf nicht nur happy path sein | keep |
| H5P Backend und Sidecar | `backend/tests/test_h5p_*`, `h5p-service/test/*.test.mjs` | H5P-Routen, Assets, Auth, Cookies und Sidecar-Verträge schützen | Contract, Adapter, H5P-Service | Node, teils Compose | teils `e2e` | `frontend-h5p`, `full-prod-like` | eigene Runtime kann durch Backend-only-Tests übersehen werden | keep |
| Frontend Vitest und SvelteKit | `frontend/src/**/*.test.ts` | Komponenten, Route-Contracts, BFF-Proxy und UI-Zustände schützen | Frontend | Node/jsdom | keiner | `frontend-h5p` | aktuell noch nicht hart genug im Haupt-Verify | keep |
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
