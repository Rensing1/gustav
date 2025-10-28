# Plan: Learning limit clamp & rubric criteria visibility

## Kontext
Review deckte zwei Must-Fixes auf:
- `limit` in `ListCoursesUseCase` wird bei 50 gekappt, obwohl der OpenAPI-Vertrag 100 erlaubt.
- Rubrik-Kriterien fehlen bei Lernenden-Abfragen, weil `_fetch_task_criteria` direkt die RLS-geschützte Tabelle `unit_tasks` abfragt.

## Ziele
1. Pagination-Clamping auf 100 heben, inklusive Tests & Vertragsprüfung.
2. Kriterien über eine studententaugliche Funktion bereitstellen (API- & Repo-Anpassung, Migration, Tests).

## Arbeitspakete
- Analyse bestehender Tests & Verträge.
- Limit-Clamp Fix und Test aktualisieren.
- SQL-Helper für Kriterien (inkl. Migration + RLS-Safety) und Repo-Anpassung.
- Tests: API-Verhalten, Rubrik-Ausgabe (text+image).
- Dokumentation & Changelog nachziehen.

## Nicht-Ziele
- Keine UI-Änderungen über Tests hinaus.
- Kein Refactoring außerhalb Limit-/Rubrik-Kontext.

## Risiken
- Migrationen müssen idempotent und mit bisherigen Policies kompatibel bleiben.
- Helper darf keine unbefugten Daten preisgeben (nur eigene Tasks, released sections).
