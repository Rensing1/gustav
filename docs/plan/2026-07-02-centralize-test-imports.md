# Centralize Test Imports

Status: Implemented as first PR 9 slice in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/packaging/test_test_import_paths_contract.py`, `make test-import-boundaries`
CI status: `make harness-minimum` prüft den schnellen Contract; `make verify` führt das Import-Boundary-Gate aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-package-oriented-app-start.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`
Review cadence: nach jedem gezielten Test-Import-Cleanup

## Zweck
PR 9 verhindert, dass pytest eine unsichtbare zweite Importwelt pflegt. Der erste Schritt zentralisiert den noch notwendigen Importpfad-Bootstrap in `backend/tests/import_paths.py`. Dadurch bleiben historische Kompatibilitätspfade sichtbar, erklärbar und später entfernbar, statt in `conftest.py` und einzelnen Tests weiter zu wachsen.

## User Story
Als Produktverantwortlicher will ich, dass Tests dieselbe Package-Struktur wie Docker und Produktion anstreben, damit IDEs, Container und pytest dieselben Importgrenzen anzeigen und neue Tests keine lokalen Import-Crutches einführen.

## BDD-Szenarien
- Given pytest startet, when `conftest.py` geladen wird, then delegiert es Importpfad-Setup an `backend.tests.import_paths.configure_test_import_paths`.
- Given alte Tests noch flache Imports verwenden, when pytest läuft, then bleiben die temporären Kompatibilitätspfade zentral dokumentiert.
- Given ein neuer Test lokale `sys.path`-Manipulationen einführt, when `make test-import-boundaries` läuft, then wächst die `sys_path_mutations`-Baseline und das Gate schlägt fehl.
- Given Test-Imports schrittweise bereinigt werden, when die Baseline neu gemessen wird, then darf sie nur sinken oder stabil bleiben, aber nicht wachsen.

## Teststrategie
- Rot: `backend/tests/packaging/test_test_import_paths_contract.py` fordert einen zentralen Importpfad-Helper und verbietet direkte `sys.path.insert`-/`append`-Aufrufe in `conftest.py`.
- Grün: `backend/tests/import_paths.py` kapselt die bestehenden pytest-Kompatibilitätspfade und `conftest.py` ruft nur noch `configure_test_import_paths()` auf.
- Refactor: Die Import-Boundary-Baseline bleibt unverändert; keine Kategorie wird durch die Zentralisierung erhöht.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/packaging/test_test_import_paths_contract.py` → 2 failed, weil Helper und Delegation fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/packaging/test_test_import_paths_contract.py backend/tests/test_auth_default_app_base.py backend/tests/test_routes_repo_set_repo_contract.py` → 8 passed.
- Grün: `.venv/bin/python -m backend.tools.import_boundary_scan --json` → `flat_routes_imports=356`, `flat_components_imports=0`, `backend_web_routes_imports=22`, `sys_path_mutations=110`.
- Grün: `make test-import-boundaries` → `import-boundary-scan-ok`.
- Grün: `make harness-minimum` → 89 passed; Docker-Compose-Konfiguration valide.

## Offene Arbeit
- Alte Tests dateigruppenweise von `routes.*`, `identity_access.*` und `teaching.*` auf package-orientierte Imports umstellen.
- Danach `backend/tests/import_paths.py` verkleinern: zuerst `WEB_DIR`, dann `BACKEND_DIR`, zuletzt `TESTS_DIR`, sofern keine Tests mehr davon abhängen.
- Nach jedem Cleanup `docs/harness/IMPORT_BOUNDARY_BASELINE.json` senken und `docs/harness/IMPORT_INVENTORY.md` aktualisieren.
