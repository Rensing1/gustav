# Plan: Teaching Modular Editor - Edges fehlen nach Reload (2026-02-13)

Status: abgeschlossen (2026-02-13)

## Ziel
- Das Problem reproduzierbar dokumentieren: Im Lehrer-Editor fuer modulare Lerneinheiten werden persistierte Kanten nach Seiten-Reload nicht gerendert.
- Die technische Root-Cause klar benennen.
- Einen minimalen, testgetriebenen Fix-Plan (Red-Green-Refactor) festlegen.

## Problemzusammenfassung
- Beobachtung: Kanten sind direkt nach dem Erstellen sichtbar.
- Fehlerbild: Nach Browser-Reload der Editor-Seite sind dieselben Kanten nicht mehr sichtbar.
- Erwartung: Persistierte Kanten muessen nach Reload aus SSR-Daten geladen und sofort gerendert werden.

## Relevanter Kontext (Code + Historie)
- SSR rendert Kanten-Daten in einem `<template>`:
  - `backend/web/main.py:3489`
  - `<template id="modular-editor-edges-data">{edges_json}</template>`
- JS liest Kanten aktuell so ein:
  - `backend/web/static/js/teaching_modular_unit_editor.js:13`
  - Parser nutzt `el.textContent`.
- CSP-Entscheidung im Plan:
  - `docs/plan/2026-02-06-PR-fix.md:14`
  - Inline-Skripte vermeiden, SSR-JSON in nicht-ausfuehrendem Container (`template`) ablegen.
- Vorheriger Fix-Versuch:
  - Commit `6654b61`: "persist edges across reload"
  - Commit `7bf3c7e`: Security-Fix, Wechsel zu `<template>`.
- Vorhandener Test:
  - `backend/tests/test_teaching_modular_unit_editor_edges_ssr.py`
  - Test prueft, dass JSON im HTML eingebettet ist.
  - Test prueft nicht, ob die JS-Seite das `template` korrekt parst und rendert.

## Root-Cause
- `HTMLTemplateElement` speichert Inhalte in `el.content`.
- `el.textContent` auf dem `<template>` selbst ist leer.
- Konsequenz:
  - Reload-Pfad: JS parst leere Daten -> `edges = []` -> kein SVG-Rendering.
  - Create-Pfad: JS pusht API-Antwort direkt in den In-Memory-State -> Kante sichtbar bis Reload.

Kurzform:
- SSR-Daten vorhanden.
- Parser liest falsche Property fuer `template`.
- Deshalb tritt der Fehler nur nach Reload auf.

## Scope
- Frontend-Parser fuer Editor-Kanten robust gegen `template` machen.
- Tests erweitern, damit dieser Fehler nicht erneut unbemerkt bleibt.

## Non-Goals
- Keine Aenderung an Edge-API, DB-Schema, Migrationen oder Unlock-Logik.
- Kein groesseres UI-Refactoring.

## User Story
Als Lehrkraft moechte ich nach einem Reload im modularen Editor weiterhin alle bestehenden Kanten sehen, damit ich den Graph konsistent bearbeiten kann.

## BDD-Szenarien
1. Reload-Happy-Path
   Given eine modulare Unit mit persistierter Kante A -> B
   When ich die Editor-Seite neu lade
   Then wird A -> B ohne erneutes Erstellen sichtbar gerendert

2. Robustheit bei leerem SSR-Container
   Given der SSR-Container existiert, aber ist leer
   When die Seite initialisiert
   Then crasht der Parser nicht und liefert eine leere Kantenliste

3. Robustheit bei ungueltigem JSON
   Given der SSR-Container enthaelt ungueltiges JSON
   When die Seite initialisiert
   Then crasht der Parser nicht und liefert eine leere Kantenliste

## Loesungsentwurf (Red-Green-Refactor)
1. Red
- JS-Contract-Test ergaenzen:
  - Wenn Quelle ein `<template id="modular-editor-edges-data">` ist, muss der Parser JSON aus `template.content` lesen.
- Optional UI-Regressionstest:
  - Nach Reload existiert mindestens ein SVG-Pfad `.modular-editor__edge` fuer persistierte Kanten.

2. Green (minimal)
- In `parseEdges(root)` Parser anpassen:
  - Wenn Element ein `template` ist, zuerst `el.content.textContent` lesen.
  - Sonst auf `el.textContent` (und optional `el.innerHTML`) fallen.
- Kein weiterer Umbau im Rendering.

3. Refactor
- Parser kapseln und defensiv halten (ein klarer Einstiegspunkt fuer SSR-Edge-Daten).
- Kommentierung knapp ergaenzen: warum `template.content` benoetigt wird.

## Testplan
- Zielgerichtet:
  - `backend/tests/test_teaching_modular_unit_editor_edges_ssr.py` (bestehender SSR-Einbettungstest)
  - Neuer JS-Contract-Test fuer `template.content`-Parsing
- Optional breiter:
  - relevante Teaching-UI Contract-Tests fuer modularen Editor

## Akzeptanzkriterien
- Persistierte Kanten sind nach Reload sichtbar.
- Kein Regression bei frisch erstellten/entfernten Kanten im laufenden Editor.
- Test-Suite enthaelt einen Guard, der `template`-Parsing explizit absichert.

## Risiken und Mitigation
- Risiko: Fix nur fuer `template`, spaetere Container-Aenderungen brechen erneut.
  - Mitigation: Parser mit klaren Fallbacks + Test fuer erwarteten Container-Typ.
- Risiko: Reine SSR-Regex-Tests decken Runtime-Verhalten nicht.
  - Mitigation: Mindestens ein JS-Contract-Test auf Parser-Ebene.

## Umsetzung (abgeschlossen am 2026-02-13)
- Green-Fix umgesetzt:
  - `backend/web/static/js/teaching_modular_unit_editor.js`
  - `parseEdges(root)` liest jetzt fuer `<template>` zuerst `el.content.textContent`, mit defensivem Fallback auf `el.textContent`.
- Neuer Regressionstest umgesetzt (Node-Behavior):
  - `backend/tests/test_teaching_modular_unit_editor_js_behaviour.py`
  - Deckt ab:
    - Reload-Happy-Path (Template-Content wird geparst)
    - leerer Container -> `[]`
    - ungueltiges JSON -> `[]`
- Verifikation:
  - `.venv/bin/pytest -q backend/tests/test_teaching_modular_unit_editor_js_behaviour.py` -> `3 passed`
  - `.venv/bin/pytest -q backend/tests/test_teaching_modular_editor_contract.py backend/tests/test_teaching_modular_unit_editor_edges_ssr.py` -> `4 passed, 1 skipped`
