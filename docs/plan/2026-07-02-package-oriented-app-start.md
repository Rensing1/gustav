# Package-Oriented App Start

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/packaging/test_import_paths_contract.py backend/tests/test_docker_image_smoke_contract.py`, `make test-docker-image-smoke`
CI status: `make harness-minimum` prüft die schnellen Packaging-Contracts; `make verify` führt `make test-docker-image-smoke` als hartes Packaging-Gate aus.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-import-inventory-boundaries.md`, `docs/plan/2026-07-02-docker-image-only-smoke.md`
Review cadence: nach Abschluss von PR 8

## Zweck
PR 8 dreht den Web-Runtime-Start konsequent von flachen `main:app`-/`routes.*`-Imports auf einen package-orientierten Start mit `backend.web.main:app`. Damit wird der Docker-Start näher an der Repository-Struktur und reduziert das Risiko doppelter Modulinstanzen durch gemischte Importnamen. Web und Learning-Worker mounten das Backend lokal jeweils als ein einziges Package unter `/app/backend`; einzelne Subpackage-Mounts sind absichtlich entfernt, damit IDE, Docker-Image und Container-Laufzeit dieselbe Struktur sehen.

## Produktentscheidung
Der gewählte Ansatz ist der harte Import-Schnitt: flache Web-Imports werden nicht als neue Normalität beibehalten. Wo PR 8 Dateien anfasst, werden Web-Adapter-Imports auf `backend.web.*` umgestellt. PR 9 bleibt für die zentrale Test-Import-Konfiguration und das schrittweise Entfernen verstreuter `sys.path`-Manipulationen zuständig.

## User Story
Als Produktverantwortlicher will ich, dass GUSTAV im Docker-Image über `backend.web.main:app` startet, damit lokale Tests, Image-Smoke und Produktionsstart dieselbe package-orientierte Architektur verwenden.

## BDD-Szenarien
- Given das Docker-Image wird gebaut, when der Container startet, then startet Uvicorn `backend.web.main:app`.
- Given kritische Imports im Image geprüft werden, when der Image-Smoke läuft, then importiert er `backend.web.main` statt `main`.
- Given Web-Adapter-Code neue Imports nutzt, when Packaging-Contracts laufen, then enthalten berührte Web-Dateien keine flachen `routes.*`, `components`, `auth_utils`, `config`, `storage_wiring`, `material_file_access` oder `evidence_rendering`-Imports mehr.
- Given Docker Compose lokale Entwicklung startet, when der Web-Service gemountet wird, then gibt es nur ein Backend-Mount unter `/app/backend` und keine doppelten Top-Level-Mounts für `identity_access` oder `teaching`.
- Given Docker Compose lokale Entwicklung startet, when der Learning-Worker gemountet wird, then gibt es auch dort nur ein Backend-Mount unter `/app/backend` und keine einzelnen Subpackage-Mounts für `learning`, `vision`, `storage`, `scratch`, `makecode`, `filius` oder `backend/__init__.py`.
- Given Tests oder Altpfade noch beide Modulnamen kennen, when der package-orientierte Start aktiv ist, then darf `main` nur noch als Legacy-Alias auf dieselbe Modulinstanz zeigen, nicht als Runtime-Startziel.

## Teststrategie
- Rot: Packaging-Contracts fordern `backend.web.main:app`, package-orientierte Docker-Kopien und das Ende flacher produktiver Web-Imports.
- Grün: Dockerfile kopiert das Backend als Package, startet `uvicorn backend.web.main:app` und reduziert `PYTHONPATH` auf `/app`.
- Grün: Web-Adapter-Imports in `backend/web` werden auf `backend.web.*` umgestellt.
- Grün: Produktiver Backend-Code nutzt `backend.identity_access.*` und `backend.teaching.*`; Dockerfile und Compose erzeugen keine Top-Level-Duplikate oder Worker-Submount-Duplikate mehr.
- Refactor: Import-Baseline wird nach erfolgreichem Lauf aktualisiert, damit künftige flache Import-Rückfälle blockiert werden.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/packaging/test_import_paths_contract.py backend/tests/test_docker_image_smoke_contract.py` schlug zunächst fehl, weil Dockerfile, Compose, Smoke-Script und Web-Imports noch den flachen Start erwarteten.
- Grün: `.venv/bin/pytest -q backend/tests/packaging/test_import_paths_contract.py backend/tests/test_docker_image_smoke_contract.py backend/tests/test_import_boundary_gate_contract.py backend/tests/test_makefile_targets.py` → 22 passed.
- Grün: `make test-import-boundaries` → `import-boundary-scan-ok`.
- Grün: `.venv/bin/python -c "import backend.web.main; import sys; print(sys.modules['main'] is backend.web.main)"` → `True`.
- Grün: `make test-docker-image-smoke` → Image gebaut, `backend.web.main` und kritische Backend-Packages ohne Volumes importiert, `package-roots-ok` für fehlende `/app/identity_access`- und `/app/teaching`-Dubletten, `/health` erreichbar.
- Grün: `.venv/bin/pytest -q backend/tests/test_auth_default_app_base.py backend/tests/test_auth_middleware.py backend/tests/test_auth_cookie_policies.py backend/tests/test_routes_repo_set_repo_contract.py backend/tests/test_app_storage_wiring.py backend/tests/test_learning_routes_helpers.py` → 52 passed.
- Grün: `.venv/bin/pytest -q backend/tests/test_learning_worker_packaging_contract.py backend/tests/packaging/test_import_paths_contract.py backend/tests/test_docker_image_smoke_contract.py` → 12 passed.
- Grün: Der lokale Schattenbaum `backend/web/backend/` wurde entfernt; `backend/tests/packaging/test_import_paths_contract.py` und `backend/tests/test_learning_worker_packaging_contract.py` → 7 passed.

## Restrisiko
Viele Backend-Tests importieren historisch noch `routes.*`. PR 8 räumt produktive Web-Imports und Packaging auf; PR 9 zentralisiert anschließend die Test-Import-Konfiguration und entfernt verstreute Test-Crutches. `backend/web/backend/__init__.py` ist aus dem Git-Index entfernt; der frühere lokale Schattenbaum `backend/web/backend/` ist ebenfalls entfernt, damit IDEs keine zweite Backend-Paketwurzel mehr analysieren.
