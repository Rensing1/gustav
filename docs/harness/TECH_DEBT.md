# Tech Debt

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument macht bewusst akzeptierte Abweichungen sichtbar. Der aktuelle Harness-Stand akzeptiert keine offenen Abweichungen als Restarbeit des Refactor-Plans.

## Aktueller Stand

Keine offenen Tech-Debt-Einträge.

## Vorlage für neue Einträge

Neue Einträge müssen als Tabelle mit diesen Spalten angelegt werden:

- ID
- Bereich
- Risiko
- Grund
- Owner
- Review date
- Exit criterion

Jeder Eintrag braucht ein konkretes Exit-Kriterium und darf nur eine bewusst akzeptierte, zeitlich überprüfbare Abweichung beschreiben. Wenn ein Eintrag nötig wird, beginnt die echte Tabelle mit `| ID | Bereich | Risiko | Grund | Owner | Review date | Exit criterion |`; solange keine echte Tabelle vorhanden ist, zählt die Scorecard null offene Einträge.
