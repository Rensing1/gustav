# Plan: Student Graph - Knoten pro Phase zentrieren (2026-02-14)

Status: umgesetzt (2026-02-14)

## Ziel
- In der modularen Schueler-Graph-Uebersicht sollen Knoten pro Phase horizontal
  zentriert werden statt linksbuendig zu starten.
- Die globale Graph-Interaktion (Pan/Zoom/Fit) bleibt unveraendert.

## Kontext
- Aktuell berechnet `buildGraphModel(...)` in
  `backend/web/static/js/student_modular_workspace.js` die X-Positionen per
  fixer Formel `BASE_X + (position_in_phase - 1) * GAP_X`.
- Dadurch wirken Phasen mit wenigen Modulen linkslastig.

## Scope
- Frontend-only:
  - `backend/web/static/js/student_modular_workspace.js`
  - `backend/tests/test_student_modular_workspace_js_contract.py`

## Non-Goals
- Keine API-/OpenAPI-Aenderung.
- Keine DB-Migration.
- Keine Aenderung an Unlock-Logik, Statusberechnung oder Sicherheitspruefungen.

## User Story
Als Schueler moechte ich, dass die Knoten jeder Phase im Graphen optisch
zentriert erscheinen, damit der Advance Organizer aufgeraeumt und leichter
lesbar wirkt.

## BDD-Szenarien
1. Happy Path
   - Given eine Phase mit unterschiedlich vielen Modulen
   - When der Graph gerendert wird
   - Then sind die Knoten innerhalb jeder Phase horizontal zentriert

2. Drift explizit erlaubt
   - Given zwei Phasen mit verschiedener Modulanzahl
   - When der Graph gerendert wird
   - Then duerfen vertikale Spalten zwischen den Phasen driften

3. Regression
   - Given bestehende Interaktion im Graph
   - When die Positionierung angepasst wird
   - Then bleiben Pan/Zoom/Fit und Kantenrendering unveraendert funktional

## Umsetzung (Red-Green-Refactor)
1. Red
   - Contract-Test erweitern:
     - Guard fuer phasenweise Zentrierungslogik.
     - Guard, dass die alte linksbuendige Formel nicht mehr genutzt wird.

2. Green
   - In `buildGraphModel(...)`:
     - Module je Phase gruppieren und nach `position_in_phase` sortieren.
     - Pro Phase Start-X aus einem festen Phasenmittelpunkt berechnen.
     - Knoten-X aus `startX + index * GAP_X` ableiten.

3. Refactor
   - Klar benannte lokale Maps/Variablen fuer Lesbarkeit.
   - Knapper Why-Kommentar zur Zentrierungsentscheidung.

## Testplan
- `.venv/bin/pytest -q backend/tests/test_student_modular_workspace_js_contract.py`
- Optional Smoke:
  - `.venv/bin/pytest -q backend/tests/test_learning_modular_unit_page_ui.py`

## Ergebnis
- Implementierung in `backend/web/static/js/student_modular_workspace.js`:
  - X-Positionierung ist nun phasenweise zentriert.
  - Alte linksbuendige Formel wurde ersetzt.
- Tests:
  - `.venv/bin/pytest -q backend/tests/test_student_modular_workspace_js_contract.py` -> 6 passed
  - `.venv/bin/pytest -q backend/tests/test_learning_modular_unit_page_ui.py` -> 7 passed
