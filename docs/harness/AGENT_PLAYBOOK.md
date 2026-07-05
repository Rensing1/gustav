# Agent Playbook

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Playbook beschreibt den Standardablauf für Agentenarbeit an GUSTAV.

## Arbeitsablauf
1. Kontext lesen: `AGENTS.md`, passende Harness-Dokumente, passende Pläne und betroffene Tests.
2. User Story und BDD-Szenarien formulieren, wenn fachliches Verhalten geändert wird.
3. API-Änderungen zuerst in `api/openapi.yml` planen und testen.
4. Red-Green-Refactor: erst Test, dann minimale Umsetzung, dann Aufräumen.
5. Sicherheits- und Datenschutzrisiken explizit prüfen.
6. Verifikation frisch ausführen und die Ergebnisse berichten.

## Git-Sicherheit
Arbeite mit vorhandenen Änderungen, ohne fremde Änderungen zurückzusetzen. Direkte Arbeit auf `master` ist nur zulässig, wenn der Produktverantwortliche sie ausdrücklich erlaubt.

## Finaler Bericht
Der Bericht nennt geänderte Dateien, relevante Tests, nicht ausgeführte Checks und Restrisiken.
