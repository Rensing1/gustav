# Import Inventory

Status: Draft
Owner: Produktverantwortlicher
Local checks: `make test-import-boundaries`
CI status: `make harness-minimum` prüft den Scanner-Contract; `harness-signals` führt den Import-Scan warning-only aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Inventar macht Import-Schulden zählbar. PR 6 behebt die Schulden nicht breitflächig; es verhindert, dass neue Verstöße unbemerkt hinzukommen.

## Baseline vom 2026-07-04
Die maschinenlesbare Baseline liegt in `docs/harness/IMPORT_BOUNDARY_BASELINE.json`.

| Kategorie | Anzahl | Bedeutung |
| --- | ---: | --- |
| `flat_routes_imports` | 291 | Flache `routes.*`-Imports, derzeit noch in Tests. Produktiver Web-Code startet package-orientiert. |
| `flat_components_imports` | 0 | Flache `components`-Imports wurden aus produktivem Web-Code entfernt. |
| `backend_web_routes_imports` | 6 | `backend.web.routes.*`-Imports außerhalb des Web-Adapters, vor allem Tests; innerhalb des Web-Adapters ist dieser Stil nach PR 8 Zielzustand. |
| `sys_path_mutations` | 50 | Verstreute `sys.path`-/`os.sys.path`-Manipulationen, vor allem in Tests. |

## Gate
`make test-import-boundaries` führt `backend.tools.import_boundary_scan` gegen die Baseline aus. Das Target schlägt fehl, wenn eine Kategorie über die Baseline wächst. In `harness-signals` ist derselbe Check warning-only sichtbar.

## Zentrale Test-Import-Konfiguration
`backend/tests/import_paths.py` ist seit PR 9 die einzige zentrale Stelle für pytest-Importpfad-Bootstrap. Die Datei enthält noch temporäre Kompatibilitätspfade für historische Tests; neue Tests dürfen keine eigenen `sys.path`-Manipulationen hinzufügen. Das Import-Boundary-Gate blockiert Wachstum der Kategorie `sys_path_mutations`.

## Zielbild
- Der Docker-Start ist `backend.web.main:app`.
- Produktiver Web-Code importiert Web-Module über `backend.web.*`.
- Neue Tests sollen keine weiteren verstreuten `sys.path`-Manipulationen einführen.
- Neue produktive Web-Routen dürfen keine flachen `routes.*`-Imports einführen.

## Offene Arbeit
- Einzelne Testgruppen auf zentrale Test-Import-Konfiguration umstellen.
- Test-Imports von `routes.*` auf package-orientierte Imports umstellen.
- Baseline nach jedem gezielten Import-Cleanup senken.
