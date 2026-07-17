# AI Harness

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: Keine anbietergebundene CI erforderlich; die lokalen Make-Ziele sind maßgeblich
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Der AI Harness beschreibt die Umgebung, in der Agenten an GUSTAV arbeiten: Kontext, Werkzeuge, Autonomie, Evidenz, Skills, Prüfungen und menschliche Review.

## Rollen
- Planner: zerlegt Arbeit in kleine, testbare Schritte.
- Implementer: arbeitet test-first und verändert nur den geplanten Ausschnitt.
- Verifier: prüft Tests, lokale Gates, Verifikationssignale und Restrisiken.
- Reviewer: sucht Fehler, Sicherheitslücken, Architekturverletzungen und fehlende Tests.
- Doc Gardener: hält Harness-, Plan- und Debt-Dokumente aktuell.

## Autonomie
Autonomie folgt `docs/harness/AUTONOMY_MATRIX.md`, nicht der Identität eines bestimmten Agenten. Skills erweitern keine Berechtigungen.

## Evidenz
Jede nicht-triviale Änderung nennt gelesene Kontextdateien, ausgeführte Befehle, Fehlschläge, Attribution der Fehlschläge, geänderte Dateien, Verifikation und Restrisiken.

## Skills
Offizielle GUSTAV-Skills leben unter `docs/harness/skills/<skill>/SKILL.md`, werden in `docs/harness/SKILLS.md` inventarisiert und brauchen Forward-Test-Evidenz in `docs/harness/SKILL_EVALS.md`.

## Eskalation
Agenten eskalieren Produkt-, Datenschutz-, Rollen-, Breaking-API-, DB-/Migrations-, Security-Ausnahme- und Bewertungsentscheidungen an den Produktverantwortlichen.
