# Harness Index

Status: Draft
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`, `docs/plan/2026-07-02-harness-minimum-implementation.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument ist die Fünf-Minuten-Startseite für Agenten und Entwickler. Es zeigt, wo Regeln, Gates, Autonomiegrenzen und offene Refactor-Pläne liegen.

## Lesereihenfolge
1. `AGENTS.md` für die verbindlichen Repository-Regeln.
2. `docs/harness/AI_HARNESS.md` für Rollen, Autonomie, Evidenz und Eskalation.
3. `docs/harness/AGENT_PLAYBOOK.md` für den praktischen Arbeitsablauf.
4. `docs/harness/QUALITY_GATES.md` und `docs/harness/TEST_STRATEGY.md` für lokale Checks.
5. `docs/harness/ARCHITECTURE_RULES.md`, `docs/harness/IMPORT_INVENTORY.md`, `docs/harness/ROUTE_MAP.md` und `docs/harness/DB_TEST_INVENTORY.md` für Import-, Architektur-, Route-Surface- und DB/RLS-Testgrenzen.
6. `docs/harness/DATA_INVENTORY.yml` für personenbezogene Daten, LLM-Grenzen, Retention, Export und Löschung.
7. `docs/harness/QUALITY_SCORECARD.md` und `docs/harness/QUALITY_SCORECARD_HISTORY.json` für den monatlichen Qualitätsüberblick.
8. `docs/harness/SKILLS.md` und `docs/harness/SKILL_EVALS.md` für repo-gesteuerte Skills.
9. `docs/plan/INDEX.md`, `docs/plan/MILESTONES.md` und `docs/plan/DECISIONS.md` für aktuelle Planung.

## Kritische Gates
- Hard: `make harness-minimum`
- Import-Baseline: `make test-import-boundaries`
- API-Contract-Baseline: `make test-api-contract-baseline`
- Architektur-Boundaries: `make test-architecture-boundaries`
- DB/RLS-Testinventar: `make test-db-inventory`
- Warning-only: `make harness-signals`
- Vollständig produktionsnah: `make verify`

## Stop- und Eskalationsregeln
Stoppe und eskaliere an den Produktverantwortlichen, wenn eine Änderung Produktentscheidungen, Rollenmodell, Datenschutz/Retention, Breaking APIs, Migrationen, Security-Ausnahmen oder pädagogische Bewertungslogik verändert.
