# Tech Debt

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument macht bewusst akzeptierte Abweichungen sichtbar.

## Vorlage
| ID | Bereich | Risiko | Grund | Owner | Review date | Exit criterion |
| --- | --- | --- | --- | --- | --- | --- |
| TD-001 | Harness PR 1 | Warning-Signale blockieren noch nicht | Erstes Harness soll Orientierung schaffen, ohne laufende Refactors zu blockieren | Produktverantwortlicher | 2026-08-02 | `make harness-signals` ist stabil und einzelne Signale sind als harte Gates eingeordnet |
