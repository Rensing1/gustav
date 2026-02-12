# Plan: H5P-History im Schueler-UI entfernen (2026-02-08)

Status: abgeschlossen (Hinweis ergänzt am 2026-02-12)

## Ziel
- H5P-Aufgaben sollen keinen "Versuch"-Block (History-Accordion) mehr anzeigen.
- Andere Aufgabenarten bleiben unveraendert.

## Kontext
- H5P-Abgaben werden per `fetch` gespeichert und erzeugen aktuell einen neuen
  History-Eintrag in der Task-Accordion-UI.
- Das fuehrt zu verwirrenden "Versuch"-Bloecken im Schueler-UI.

## Scope
- SSR-UI: History-Placeholder fuer H5P-Tasks unterdruecken.
- Tests: H5P-spezifischer Guard + Regression fuer Nicht-H5P.

## Non-Goals
- Keine Aenderungen an API, DB, Unlock-Logik oder H5P-Service.
- Keine neuen E2E-Tests.

## User Story
Als Schueler moechte ich nach einer H5P-Abgabe keinen neuen "Versuch"-Block sehen,
damit die UI nicht unnoetig komplex wirkt.

## BDD-Szenarien
1. Happy Path (H5P)
   Given eine H5P-Aufgabe in einer Einheit
   When die Einheit gerendert wird
   Then es gibt keinen "task-history-..."-Block fuer diese Aufgabe

2. Regression (Nicht-H5P)
   Given eine normale Text-Aufgabe in einer Einheit
   When die Einheit gerendert wird
   Then der "task-history-..."-Placeholder ist weiterhin vorhanden

## Umsetzung (Red-Green-Refactor)
1. Red: UI-Test fuer H5P-Tasks ohne History-Placeholder.
2. Red: Regressionstest fuer Nicht-H5P-Tasks mit History-Placeholder.
3. Green: SSR-Renderlogik fuer H5P-Tasks so anpassen, dass keine History
   gerendert wird.

## Testplan
- `.venv/bin/pytest -q backend/tests/test_learning_ui_student_submissions.py -k h5p`
- `.venv/bin/pytest -q backend/tests/test_learning_ui_student_submissions.py -k non_h5p`

## Rollout
- Normales Deployment, keine Migrationen.
