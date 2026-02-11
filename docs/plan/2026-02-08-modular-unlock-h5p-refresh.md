# Plan: H5P unlock refresh in modular workspace (2026-02-08)

## Ziel
- Nach erfolgreicher H5P-Abgabe muss der modulare Graph im selben View aktualisiert werden.
- Kein Reload noetig; nur ein UI-Event, keine Backend-Aenderungen.

## Kontext
- Der Graph-Refresh wird aktuell nur durch den HTMX-Submit-Flow getriggert.
- Der H5P-Submit nutzt `fetch` und emittiert kein `modularGraphRefresh`.
- Listener sitzt auf `.modular-unit-page` und erwartet `detail: { courseId, unitId }`.

## Scope
- Frontend-only: `h5p_task_player.js` ergaenzen.
- Ein minimaler Contract-Test als String-Guard.

## Non-Goals
- Keine Aenderungen an Unlock-Logik, API, DB oder Migrationen.
- Keine neue E2E-Testinfra.

## User Story
Als Schueler moechte ich, dass nach einer erfolgreichen H5P-Abgabe die
naechsten Module sofort als offen sichtbar werden, ohne die Seite neu zu laden.

## BDD-Szenarien
1. Happy Path
   Given Modul A (H5P) unlockt Modul B
   When H5P submit erfolgreich (full score)
   Then Modul B wird ohne Reload als offen sichtbar

2. Failure Safety
   Given H5P submit scheitert (non-2xx)
   When submitAttempt wirft
   Then kein Refresh-Event wird emittiert

3. Regression
   Given HTMX-Submit fuer non-H5P
   Then bestehender Refresh-Flow bleibt unveraendert

## Umsetzung (Red-Green-Refactor)
1. Red: Contract-Test, der `modularGraphRefresh`-Dispatch im H5P-Player erwartet.
2. Green: Nach erfolgreichem H5P-Submit ein CustomEvent emittieren.
3. Refactor: Minimal halten, keine weitere Logik.

## Testplan
- `.venv/bin/pytest -q backend/tests/test_h5p_task_player_refresh_event_contract.py`
- Optional: bestehende H5P-Contract-Tests mitlaufen lassen.

## Rollout
- Normales Frontend Asset Busting (JS-Version). Keine weiteren Schritte.
