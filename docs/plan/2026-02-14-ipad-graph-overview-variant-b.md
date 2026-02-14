# Plan: iPad Graph-Uebersicht optimieren (Variante B) (2026-02-14)

Status: umgesetzt (2026-02-14)

## Ziel
- In der modularen Schueler-Ansicht soll die Graph-Uebersicht auf iPads sichtbar mehr Flaeche erhalten.
- Breadcrumb und Footer bleiben sichtbar, werden im Overview-Modus aber kompakter.

## Kontext
- Die Seite nutzt in Overview bereits `mode-overview` (Scroll-Lock + flex layout).
- Trotz Flex-Regeln belegen Header/Toolbar + globaler Seiten-Chrome (Breadcrumb/Footer) zu viel Hoehe.
- Schuelerfeedback: Graph wirkt auf iPads zu klein.

## Scope
- Frontend-only:
  - `backend/web/static/css/student_modular_unit.css`
  - `backend/web/components/layout.py` (Asset-Busting)
  - `backend/tests/test_student_modular_unit_css_contract.py`

## Non-Goals
- Keine API-Aenderung (`api/openapi.yml` unveraendert).
- Keine DB-Migration.
- Keine Aenderung an Unlock-Logik oder modularen Endpunkten.

## User Story
Als Schueler auf dem iPad moechte ich in der Graph-Uebersicht mehr nutzbare
Flaeche sehen, damit ich Module und Kanten besser erfassen kann, ohne dass
Footer/Breadcrumb vollstaendig verschwinden.

## BDD-Szenarien
1. Happy Path (mehr Graphflaeche)
   - Given ich bin auf iPad in einer modularen Lerneinheit
   - When ich den Modus "Uebersicht" nutze
   - Then ist der vertikale Platz fuer den Graphen groesser als zuvor

2. Kompakt statt hidden
   - Given ich bin im Overview-Modus
   - When die Seite gerendert wird
   - Then Breadcrumb/Footer bleiben sichtbar und werden nur komprimiert

3. Keine Seiteneffekte
   - Given ich bin nicht im Overview-Modus oder nicht im iPad-Breakpoint
   - When die Seite gerendert wird
   - Then gilt das bestehende Layout unveraendert

## Umsetzung (Red-Green-Refactor)
1. Red
   - Neue CSS-Contract-Tests fuer iPad-Overview:
     - kompakter Seiten-Chrome (`main-content`, `breadcrumb`, `content-footer`, `footer-content`)
     - kompakter Bereich ueber dem Graphen (`unit-head`, `unit-title`, `sticky-toolbar`, `sticky-toolbar__inner`, `graph-overlay--top`)
     - Guard: kein `display: none` fuer Breadcrumb/Footer in `html.mode-overview`

2. Green
   - Neue iPad-spezifische CSS-Regeln in:
     - `@media (min-width: 768px) and (max-width: 1366px)`
     - nur im Kontext `html.mode-overview`
   - Reduzierte Abstaende/Paddings fuer Seiten-Chrome und Header/Toolbar.

3. Refactor
   - Strukturierte CSS-Sektion "Overview iPad compact chrome" mit Why-Kommentar.
   - CSS-Asset-Version in Layout hochgezogen fuer sauberes Cache-Busting.

## Testplan und Ergebnis
- `.venv/bin/pytest -q backend/tests/test_student_modular_unit_css_contract.py`
  - Ergebnis: 5 passed
- `.venv/bin/pytest -q backend/tests/test_student_modular_workspace_js_contract.py`
  - Ergebnis: 5 passed
- `.venv/bin/pytest -q backend/tests/test_learning_modular_unit_page_ui.py`
  - Ergebnis: 7 passed

## Risiken und Mitigation
- Risiko: Zu starke Verdichtung macht Bedienelemente schwerer antippbar.
  - Mitigation: nur iPad-Overview, Controls behalten ausreichende Hoehe.
- Risiko: Unbeabsichtigte globale Layout-Effekte.
  - Mitigation: harte Scope-Kombination aus `html.mode-overview` + `.modular-unit-page` + iPad-Media-Query.

## Nachjustierung (11" vs 12.9")
- Zusatzanforderung: feinere Abstimmung fuer iPad 11" und 12.9".
- Umsetzung:
  - Basisprofil (`@media (min-width: 768px) and (max-width: 1366px)`):
    - dichteres 11"-Layout (kleinere Top-Abstaende und kompaktere Toolbar-Hoehe)
  - Override fuer grosse iPads (`@media (min-width: 1024px) and (min-height: 1024px)`):
    - etwas luftigere Werte fuer 12.9"
- Zusatztetest:
  - `test_student_modular_unit_css_ipad_profiles_differentiate_11_and_12_9`
