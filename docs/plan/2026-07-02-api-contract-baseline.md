# API Contract Baseline

Status: Implemented as first PR 10 slice in working tree
Owner: Produktverantwortlicher
Local checks: `make test-api-contract-baseline`, `.venv/bin/pytest -q backend/tests/test_openapi_route_surface_baseline.py`
CI status: `make verify` führt `make test-api-contract-baseline` als hartes Gate aus; `make harness-minimum` prüft den Contract-Test.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/harness/API_CONTRACTS.md`, `docs/harness/ROUTE_MAP.md`
Review cadence: nach API- oder Route-Surface-Änderungen

## Zweck
PR 10 macht die OpenAPI-Baseline ausführbar. `api/openapi.yml` bleibt die Quelle der Wahrheit für `/api/*`; der neue Checker vergleicht die registrierten FastAPI-Runtime-Routen mit dem statischen Vertrag und klassifiziert Nicht-OpenAPI-Flächen.

## User Story
Als Produktverantwortlicher will ich, dass API-Drift zwischen Runtime und `api/openapi.yml` sofort auffällt, damit Refactorings keine stillen API-Brüche erzeugen.

## BDD-Szenarien
- Given die FastAPI-App registriert eine neue `/api/*`-Route, when `make test-api-contract-baseline` läuft, then muss dieselbe Methode und derselbe Pfad in `api/openapi.yml` vorhanden sein.
- Given `api/openapi.yml` enthält eine alte `/api/*`-Operation, when die Runtime-App sie nicht mehr registriert, then schlägt das Gate fehl.
- Given eine Route nicht in OpenAPI gehört, when sie Teil der Runtime oder des Vertrags ist, then muss sie als public API, BFF/internal, H5P service, auth bridge, health/ops, active legacy UI oder retired legacy UI klassifizierbar sein.
- Given ein Breaking Change nötig wäre, when die Semantik unklar ist, then braucht er eine Produktentscheidung und einen Eintrag in `docs/plan/DECISIONS.md`.

## Teststrategie
- Rot: `backend/tests/test_openapi_route_surface_baseline.py` forderte `test-api-contract-baseline`, ein Checker-Modul und eine Route Map.
- Grün: `backend/tools/openapi_contract_check.py` lädt `api/openapi.yml`, importiert `backend.web.main:app`, normalisiert FastAPI-Path-Konverter und vergleicht Runtime-`/api/*`-Operationen mit dem Vertrag.
- Grün: `docs/harness/ROUTE_MAP.md` dokumentiert Surface-Kategorien und die Gate-Regel.
- Refactor: `make verify` und `make harness-minimum` enthalten den neuen Contract, damit API-Drift nicht nur manuell sichtbar ist.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_openapi_route_surface_baseline.py` → 4 failed, weil Target, Checker und Route Map fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/test_openapi_route_surface_baseline.py` → 4 passed.
- Grün: `make test-api-contract-baseline` → `openapi-contract-check-ok`.
- Grün: `.venv/bin/pytest -q backend/tests/test_openapi_no_null_type.py backend/tests/test_openapi_security_headers.py backend/tests/test_openapi_internal_flags.py` → 6 passed.
- Grün: `make harness-minimum` → 93 passed; Docker-Compose-Konfiguration valide.

## Offene Arbeit
- H5P-Service-Runtime separat gegen die H5P-OpenAPI-Flächen prüfen.
- Route Map von Pattern-basierter Klassifikation zu einer vollständigen Route-für-Route-Tabelle ausbauen.
- Kritische Flows später in generische Contract-Gates zusammenführen, ohne die spezifischen Sicherheitsfälle zu verlieren.
