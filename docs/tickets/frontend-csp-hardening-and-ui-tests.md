# Ticket: Frontend CSP-Härtung & Teaching-Live-UI-Tests

## Problem

- Die Produktions-CSP ist bewusst streng (`script-src 'self'`, keine `unsafe-inline`-Ausnahmen).
- Einige Frontend-Stellen sind noch nicht vollständig CSP-konform:
  - Ältere UI-Fragmente können Inline-Skripte oder -Styles enthalten (Legacy-Bereiche).
- Für zentrale UI-Flows (z. B. „Unterricht – Live“) existieren bislang keine automatisierten UI-/E2E-Tests, die das Zusammenspiel aus CSP, HTMX und JS prüfen.

## Status (2025-12-07)

- Notifications:
  - Bereits umgesetzt: Styles aus `backend/web/static/js/gustav.js` in `backend/web/static/css/gustav.css` ausgelagert.
  - JS setzt nur noch Klassen (`notification`, `notification--exit`, `alert-*`), keine Inline-Styles mehr.
- Offene Punkte:
  - Systematisches CSP-Audit weiterer Inline-Patterns (JS/CSS).
  - UI-/E2E-Tests für Teaching-Live-Flow aufsetzen.

## Ziel

Ein CSP-sicheres Frontend ohne Inline-Skripte/-Styles und mindestens ein automatisierter UI/E2E-Test für den Teaching-Live-Flow, damit CSP- oder HTMX-bezogene Regressions frühzeitig auffallen.

## Scope

1. **CSP-Härtung Frontend**
   - Weitere Inline-Patterns:
     - Systematische Suche nach `<script>`/`style`-Attributen in SSR-Templates und statischen Assets.
     - Wo möglich: Umzug in externe JS-/CSS-Dateien.
   - Zielbild:
     - Kein Inline-JS in SSR/Partials.
     - Keine sicherheitsrelevanten Inline-Styles (mindestens für benutzerrelevante Komponenten).

2. **UI/E2E-Tests für Teaching-Live**
   - Beispiel-Flow:
     - Lehrkraft öffnet „Unterricht – Live“ für eine Einheit mit Aufgaben.
     - Schüler gibt eine Lösung ab.
     - Auto-Polling aktualisiert Matrix (`✅`) über Delta-Endpoint.
     - Klick auf eine Matrix-Zelle lädt das Detail-Panel; Tabs (Text/Datei/Auswertung/Rückmeldung) funktionieren.
   - Anforderungen:
     - Läuft unter der produktionsnahen CSP-Konfiguration.
     - Prüft sowohl Matrix-Update (Polling) als auch Tab-Verhalten.

## Nicht-Ziele

- Kein kompletter Rewrite des Frontends.
- Keine Änderung der bestehenden CSP-Policy („nicht aufweichen“), sondern Anpassung des Frontends an die Policy.

## Vorschlag Umsetzung

1. CSP-Härtung
   - Styles für Notifications in ein zentrales CSS (z. B. `backend/web/static/css/gustav-notifications.css`) auslagern.
   - In `gustav.js` nur noch Klassen setzen (`classList.add(...)`) und kein `style.cssText` mehr verwenden.
   - Audit über `rg "<script" backend/web` und statische Assets, um Inline-Skripte/-Styles systematisch zu erfassen.

2. UI/E2E-Tests
   - Test-Setup:
     - Falls vorhanden: Playwright oder ein vergleichbares Tool nutzen.
     - Alternativ: Minimaler Headless-Browser-Test (z. B. mit pytest + Playwright-Plugin).
   - Szenarien:
     - Polling: Nach Submission wird innerhalb des Polling-Intervalls die Matrix aktualisiert.
     - Tabs: Klicks auf „Auswertung“/„Rückmeldung“ blenden die entsprechenden Panels ein und andere aus.

## Risiken

- Einführung neuer Test-Infrastruktur (E2E) kann den CI-Lauf verlängern.
- UI-Tests sind naturgemäß empfindlicher gegenüber Layout-/Strukturänderungen und müssen gepflegt werden.
