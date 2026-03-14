# Plan: Spamschutz fuer Lernenden-Button "Abgeben" (SSR)

Datum: 2026-03-05
Status: implemented

## Kontext
- In der SSR-Lernansicht koennen Lernende den Button `Abgeben` mehrfach klicken.
- Ohne Schutz entstehen doppelte Requests, zusaetzliche DB-Last und unnoetige Queue-Jobs.
- Die API besitzt bereits idempotentes Verhalten ueber `Idempotency-Key`; der
  SSR-Flow nutzte bisher pro Request jedoch immer einen neuen Zufalls-Key.

## User Story
Als Lernender moechte ich bei einem Mehrfachklick auf `Abgeben` keine
Doppelabgabe erzeugen, damit meine Abgabe zuverlaessig und performant
gespeichert wird.

## Scope
- Gilt fuer SSR-Task-Formulare in `/learning/courses/{course_id}/units/{unit_id}`.
- Gilt fuer Text- und Upload-Abgaben, inklusive Scratch-/Calliope-Upload-Only.
- Nicht in Scope: globales API-Rate-Limit, H5P-Player-Submit-Flow.

## TDD
1. `backend/tests/test_learning_ui_htmx_submit.py`
   - HTMX-Attribute fuer Inflight-Schutz
   - Hidden-Field `idempotency_key`
   - SSR-Weitergabe des Form-Keys an die API
2. SSR-Formular und Submit-Route minimal anpassen
3. Client-JS fuer Locking und Key-Rotation nachziehen

## Sicherheitsnotizen
- Keine Lockerung von CSRF oder Rollenpruefungen
- Kein Logging sensibler Submission-Inhalte
- Manipulierte Hidden-Keys werden serverseitig defensiv ersetzt

## Abschluss 2026-03-14
- SSR-Formulare rendern Hidden-`idempotency_key` und HTMX-In-Flight-Schutz.
- `learning_submit_task(...)` leitet den stabilen Formular-Key an die API
  weiter, statt pro Request einen neuen Zufalls-Key zu erzeugen.
- `backend/web/static/js/gustav.js` sperrt laufende Submits und rotiert den
  Key erst nach Abschluss.
- Verifiziert mit:
  - `backend/tests/test_learning_ui_htmx_submit.py` -> `9 passed`
