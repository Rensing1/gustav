# Autonomy Matrix

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: Keine anbietergebundene CI erforderlich; die lokalen Make-Ziele sind maßgeblich
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Diese Matrix legt fest, welche Agentenhandlungen nach Risiko und Dateikategorie erlaubt sind.

## Kategorien
| Kategorie | Erlaubt | Muss eskaliert werden |
| --- | --- | --- |
| Dokumentation und Harness | planen, editieren, kleine Korrektur-PRs vorbereiten | Löschen historischer Entscheidungen |
| Tests | Regressionstests ergänzen, fehlerhafte Tests reparieren | Tests entfernen ohne Ersatzschutz |
| API | Contract-Tests und OpenAPI-Konformität prüfen | Breaking Changes |
| Security | analysieren, negative und positive Tests vorbereiten | Security-Ausnahmen oder schwächere Guards |
| DB und Migrationen | planen und Tests entwerfen | Schemaänderungen, RLS-Policy-Änderungen |
| Datenschutz | Inventar und Tests vorbereiten | Retention, Löschung, Export, LLM-Datenfluss |
| Pädagogik | Tests und Lesbarkeit verbessern | Bewertungssemantik ändern |

## Initiales Ziel
Level 1-2 für Code mit menschlicher Review, Level 3 nur für Dokumentation, Review, Planstatus und Harness-Gardening. Level 4 ist nicht Ziel von PR 1.
