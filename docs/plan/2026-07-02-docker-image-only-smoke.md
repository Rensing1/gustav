# Docker Image-Only Smoke

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_docker_image_smoke_contract.py`, `make test-docker-image-smoke`
CI status: Keine anbietergebundene CI erforderlich; Docker Image-Only Smoke bleibt zunächst ein lokaler opt-in Gate-Baustein.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 5

## Zweck
PR 5 macht sichtbar, ob das Web-Image ohne Compose-Bind-Mounts startfähig ist. Compose darf fehlende Dateien im Image nicht mehr verdecken.

## User Story
Als Produktverantwortlicher will ich ein reproduzierbares Image-only-Smoke-Signal, damit ein lokal erfolgreiches Compose-Setup nicht darüber hinwegtäuscht, dass das gebaute Produktionsimage unvollständig oder falsch verdrahtet ist.

## BDD-Szenarien
- Given das Dockerfile baut ein Web-Image, when das Image ohne Volume-Mounts gestartet wird, then kann die App ihren Health-Endpunkt bedienen.
- Given das Image wird ohne Compose-Bind-Mounts geprüft, when kritische Module importiert werden, then funktionieren `main`, `backend.learning`, `backend.vision`, `backend.storage`, `backend.scratch`, `backend.makecode` und `backend.filius`.
- Given ein Modul nur über lokale Bind-Mounts verfügbar wäre, when der Image-Smoke läuft, then schlägt der Smoke reproduzierbar fehl.

## Teststrategie
- Rot: `backend/tests/test_docker_image_smoke_contract.py` fordert ein `make test-docker-image-smoke`-Target und ein Skript, das ohne Volumes baut, Imports prüft und den Health-Endpunkt abfragt.
- Grün: `backend/tools/docker_image_smoke.py` baut ein Image, führt Import-Checks per `docker run --entrypoint python` aus und startet das Image kurz für einen Healthcheck.
- Refactor: Harness-, Meilenstein- und Masterplan-Dokumente markieren PR 5 als im Arbeitsbaum umgesetzt oder dokumentieren konkrete Image-only-Blocker.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_docker_image_smoke_contract.py` schlug fehl, weil Make-Target und Skript fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/test_docker_image_smoke_contract.py` → 2 passed.
- Harness-Contract: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py backend/tests/test_harness_test_strategy_docs_contract.py backend/tests/test_makefile_targets.py backend/tests/test_docker_image_smoke_contract.py` → 20 passed.
- CI-naher Harness: `make harness-minimum` → 72 passed und `docker compose config` OK.
- Image-only-Smoke: `make test-docker-image-smoke` → Image gebaut, kritische Imports ohne Volumes OK, `/health` erreichbar.

## Restrisiko
Der Smoke prüft bewusst nur Packaging und Startfähigkeit. Er ersetzt keine Compose-E2E-Reise, keine Supabase-Migration und keine spätere Umstellung auf package-orientierten Start mit `backend.web.main:app`.

PR 8 hat den Image-Start auf `uvicorn backend.web.main:app` mit `PYTHONPATH=/app` umgestellt. Das Image kopiert das Backend nur noch als `/app/backend`; Compose mountet denselben Package-Ort.

Der Import-Smoke läuft ohne Datenbank und sieht deshalb den erwarteten Teaching-Repo-Fallback auf In-Memory. Das ist für diesen Packaging-Smoke akzeptiert; DB-Parität bleibt Aufgabe der DB-/E2E-Gates.
