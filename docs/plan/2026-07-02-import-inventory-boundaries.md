# Import Inventory and Blocking Rules

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_import_boundary_gate_contract.py`, `make test-import-boundaries`
CI status: `make harness-minimum` prüft den Scanner-Contract; `make verify` führt `make test-import-boundaries` als hartes Baseline-Gate aus; `make harness-signals` zeigt denselben Scan warning-only.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 6

## Zweck
PR 6 macht Import-Schulden sichtbar und maschinenlesbar. Der Schritt behebt die bestehenden flachen Imports noch nicht, sondern verhindert, dass neue Verstöße unbemerkt hinzukommen.

## User Story
Als Produktverantwortlicher will ich bestehende Import-Schulden zählen und neue Verstöße blockieren, damit spätere Refactors zu `backend.web.main:app` und zentraler Test-Import-Konfiguration auf einer überprüfbaren Baseline aufbauen.

## BDD-Szenarien
- Given bestehende flache `routes.*`- und `components`-Imports im Backend, when der Import-Boundary-Scan läuft, then zählt er diese Schulden in einer stabilen Kategorie.
- Given verstreute `sys.path`-Manipulationen in Tests, when der Scan läuft, then zählt er diese Stellen als eigene Kategorie.
- Given eine neue Änderung erhöht eine Import-Schulden-Kategorie über die Baseline, when `make test-import-boundaries` oder `make verify` läuft, then schlägt der Check fehl.
- Given `make harness-signals` läuft, when der Import-Scan eine Abweichung findet, then wird sie als Warnsignal sichtbar, ohne das Signalprofil selbst hart scheitern zu lassen.

## Teststrategie
- Rot: `backend/tests/test_import_boundary_gate_contract.py` forderte ein `make test-import-boundaries`-Target, einen Scanner, eine JSON-Baseline, Dokumentation zum Ziel-Importschema und Sichtbarkeit in `make verify`.
- Grün: `backend/tools/import_boundary_scan.py` zählt die Kategorien per AST-Analyse und vergleicht sie mit `docs/harness/IMPORT_BOUNDARY_BASELINE.json`.
- Refactor: `docs/harness/IMPORT_INVENTORY.md`, `docs/harness/ARCHITECTURE_RULES.md`, `docs/harness/QUALITY_GATES.md`, `docs/harness/TEST_STRATEGY.md`, `docs/harness/TEST_PORTFOLIO.md` und die Planübersichten beschreiben die Grenze als PR6-Baseline, nicht als PR8-Entry-Point-Umbau.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_import_boundary_gate_contract.py` schlug zunächst fehl, weil Target, Scanner, Baseline und Dokumente fehlten.
- Rot: `.venv/bin/pytest -q backend/tests/test_import_boundary_gate_contract.py::test_verify_runs_import_boundary_gate` schlug fehl, weil `make verify` den Import-Boundary-Check noch nicht ausführte.
- Grün: `.venv/bin/python -m backend.tools.import_boundary_scan --json` zählte `flat_routes_imports=382`, `flat_components_imports=14`, `backend_web_routes_imports=23` und `sys_path_mutations=110`.
- Grün: `make test-import-boundaries` → `import-boundary-scan-ok`.

## Restrisiko
Der Scanner ist bewusst ein Wachstums-Gate. Er reduziert die vorhandene Import-Schuld noch nicht und bewertet keine Laufzeit-Duplikate von Modulinstanzen. Der package-orientierte App-Start mit `backend.web.main:app` bleibt Aufgabe von PR 8. Die Zentralisierung verstreuter Test-Imports bleibt Aufgabe von PR 9.
