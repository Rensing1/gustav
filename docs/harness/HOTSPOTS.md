# Hotspots

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument markiert Dateien, die im Refactor nicht weiter anwachsen sollen, ohne dass bewusst Debt dokumentiert wird.

## Initiale Hotspots
- `backend/web/main.py`
- `backend/web/routes/teaching.py`
- `backend/web/routes/learning.py`
- `backend/web/routes/app.py`
- große `repo_db.py`-Dateien
- `h5p-service/server.mjs`
- große Svelte-Routen und Komponenten
- große CSS-Dateien

## Regel
PR 1 inventarisiert die Hotspots nur. Harte LOC-Schwellen folgen, sobald Baselines und Ausnahmeprozess stabil sind.
