# Import Inventory

Status: Active
Owner: Produktverantwortlicher
Local checks: `make test-import-boundaries`
CI status: `make verify` führt `make test-import-boundaries` als hartes Gate aus; `make harness-minimum` prüft den Scanner-Contract.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`
Review cadence: monatlich

## Zweck
Dieses Inventar macht Import-Schulden zählbar und blockiert neues Wachstum. Der produktive Web-Start läuft package-orientiert über `backend.web.main:app`; Tests, Docker und Runtime verwenden denselben Namensraum.

## Baseline vom 2026-07-05
Die maschinenlesbare Baseline liegt in `docs/harness/IMPORT_BOUNDARY_BASELINE.json`.

| Kategorie | Anzahl | Bedeutung |
| --- | ---: | --- |
| `flat_routes_imports` | 0 | Flache `routes.*`-Imports sind aktuell vollständig beseitigt. |
| `flat_components_imports` | 0 | Flache `components`-Imports wurden aus produktivem Web-Code entfernt. |
| `backend_web_routes_imports` | 0 | Statische `backend.web.routes.*`-Imports außerhalb des Web-Adapters sind aus der Scanner-Baseline entfernt; Tests verwenden bei Bedarf dynamische package-orientierte Imports. |
| `sys_path_mutations` | 0 | Tests manipulieren `sys.path` nicht mehr; `backend/tests/import_paths.py` bleibt nur als no-op Guard-Hook für bestehende `conftest.py`-Aufrufe. |

## Gate
`make test-import-boundaries` führt `backend.tools.import_boundary_scan` gegen die Baseline aus. Das Target schlägt fehl, wenn eine Kategorie über die Baseline wächst. `make verify` führt dieses Gate hart aus.

## Test-Import-Konfiguration
`backend/tests/import_paths.py` enthält keine Importpfad-Mutation mehr. Bestehende Hook-Aufrufe in `conftest.py` bleiben als no-op erhalten, damit der Übergang reviewbar ist, ohne wieder lokale Sonderpfade einzuführen.

## Zielbild
- Der Docker-Start ist `backend.web.main:app`.
- Produktiver Web-Code importiert Web-Module über `backend.web.*`.
- Tests importieren App- und Bounded-Context-Module über `backend.*`.
- Neue Tests dürfen keine verstreuten `sys.path`-Manipulationen einführen.
- Neue produktive Web-Routen dürfen keine flachen `routes.*`-Imports einführen.
