# Route Surface Map

Status: Implemented as first PR 13 slice in working tree
Owner: Produktverantwortlicher
Local checks: `make test-route-map`, `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py`
CI status: `make verify` führt `make test-route-map` als hartes Gate aus; `make harness-minimum` prüft den Contract-Test.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/harness/ROUTE_MAP.md`
Review cadence: nach jedem Route-, API- oder Legacy-UI-Refactor

## Zweck
PR 13 macht die Route Map zu einer generierten Route-für-Route-Inventur. Jede Runtime- oder OpenAPI-Operation erhält Surface, Rolle, Datenzugriff, Response-Modell, Testhinweis, Risiko, Legacy-Status, Retention-/Removal-Entscheidung und Zielschicht.

## User Story
Als Produktverantwortlicher will ich vor der Monolith-Strangulation sehen, welche Routen sicherheitskritisch, legacy-lastig oder serviceextern sind, damit Refactor-Reihenfolgen nach Risiko und Nutzung entschieden werden.

## BDD-Szenarien
- Given die Runtime-App registriert eine Route, when `make test-route-map` läuft, then steht sie in `docs/harness/ROUTE_MAP.md`.
- Given `api/openapi.yml` dokumentiert eine externe H5P-Service-Route, when die Route Map generiert wird, then steht sie als H5P service in der Inventur.
- Given eine Route Schreiboperationen, Uploads, Submissions, Mitglieder oder Auth/Session betrifft, when die Route Map generiert wird, then erhält sie mindestens Risiko `high`.
- Given eine Legacy-HTML/HTMX-Route existiert noch, when die Route Map generiert wird, then ist sie active legacy UI mit Entscheidung `retain until strangled`.

## Teststrategie
- Rot: `backend/tests/test_route_map_inventory_contract.py` forderte Make-Target, Generator, synchronisierte Route Map und Pflichtspalten.
- Grün: `backend/tools/route_map_inventory.py` generiert `docs/harness/ROUTE_MAP.md` aus OpenAPI-Operationen und FastAPI-Runtime-Operationen.
- Refactor: `make test-route-map` prüft die Synchronität ohne stderr-Warnungen und `make verify` ruft das Gate hart auf.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py` → 4 failed, weil Target, Tool und generierte Tabelle fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py` → 5 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok`.
- Grün: H5P-Surface-Rollen im Generator nach Explorer-Review präzisiert: Health öffentlich, Auth-Me Principal-Bridge, Debug-Seiten admin-only, Review teacher/admin.
- Grün: Legacy-Status nach Explorer-Review präzisiert: bekannte 410-Altpfade erscheinen als `retired but still registered` mit Entscheidung `remove after characterization`, nicht als produktiv aktive Legacy-UI.
- Grün: `make harness-minimum` → 103 passed; Docker-Compose-Konfiguration valide.
- Rot: `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py` → 1 failed, weil der Generator zwar grün war, aber beim App-Import `Teaching repo unavailable ... using in-memory fallback` auf stderr ausgab.
- Grün: `backend/web/routes/teaching.py` initialisiert das Teaching-Repository nicht mehr importzeitlich; `.venv/bin/pytest -q backend/tests/test_route_map_inventory_contract.py backend/tests/test_routes_repo_set_repo_contract.py backend/tests/test_openapi_route_surface_baseline.py` → 12 passed.
- Grün: `make test-route-map` → `route-map-inventory-ok` ohne stderr-Warnung.

## Offene Arbeit
- Testabdeckung in der Route Map von Pattern-Hinweisen auf konkrete Testdateien verfeinern.
- Legacy-UI-Entscheidungen in PR 16 mit Characterization-Tests absichern.
- H5P-Service-Runtime-Parität separat gegen den Sidecar prüfen; statische Asset-Pattern-Routen wie `/h5p/webcomponents/*`, `/h5p/theme/*`, `/h5p/core/*`, `/h5p/editor-assets/*` und `/h5p/libraries/*` gehören als H5P service asset/runtime in eine spätere Sidecar-Inventur, nicht als normale OpenAPI-Operationen.
