# Plan: Teaching-Live-Detail-Tabs CSP-sicher machen

**Datum:** 2025-12-06  

## Ausgangssituation und Problem

In der Lehrkraft-Ansicht **„Unterricht › Live“** zeigt die Matrix (Schüler × Aufgaben) per Klick auf eine Zelle ein Detail-Panel unterhalb der Tabelle.  
Dieses Panel wird von der Route

- **UI (SSR):** `GET /teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…` → ruft intern  
- **API (JSON, Teaching):** `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`

versorgt.

Im aktuellen Stand:

- rendert das SSR-Partial `teaching_unit_live_detail_partial` in `backend/web/main.py` die Tabs **„Text“**, **„Datei“**, **„Auswertung“** und **„Rückmeldung“** für Lehrkräfte;  
- hängt am Ende des Fragments ein **Inline-`<script>`** an, das über `document.currentScript` die Tab-Buttons (`data-view-tab`) und Panels (`data-panel`) findet und Click-Handler registriert;  
- wird dieses Inline-Skript in der Produktionsumgebung durch die strikte **Content Security Policy** blockiert:
  - `script-src 'self'` ohne `'unsafe-inline'` in der Middleware `security_headers` in `backend/web/main.py`;  
  - in Dev ist die CSP lockerer (`script-src 'self' 'unsafe-inline'`), weshalb das Inline-Skript dort ausgeführt wird.

Resultat:

- **Dev:** Tabs funktionieren, weil Inline-Skripte erlaubt sind.  
- **Prod:** Tabs reagieren nicht auf Klicks, weil das Inline-Skript nicht ausgeführt werden darf; es gibt keine Click-Handler, und der Tab-Wechsel bleibt aus.

Dieses Verhalten ist im Ticket `docs/tickets/teaching-live-detail-tabs-csp.md` beschrieben und deckt sich mit der Analyse des Dev-Codes.

## User Story

> **Als Lehrkraft** in der Ansicht „Unterricht – Live“ möchte ich in der Produktionsumgebung zuverlässig zwischen den Detail-Tabs „Text“, „Datei“, „Auswertung“ und „Rückmeldung“ wechseln können, damit ich Schülerlösungen effizient sichten und bewerten kann – ohne die bestehende Content Security Policy zu lockern.

## BDD-Szenarien

### Happy Path: Tabs funktionieren mit strikter CSP

1. **Tabs für Text, Datei, Auswertung, Rückmeldung**
   - **Given** eine Lehrkraft ist in Prod eingeloggt, es existiert eine Lerneinheit mit Aufgaben und mindestens eine Einreichung  
   - **When** sie in „Unterricht – Live“ eine Zelle mit ✅ anklickt und danach auf den Tab „Auswertung“ klickt  
   - **Then** wechselt der sichtbare Inhalt unterhalb der Tabs zur Auswertung, der Tab „Auswertung“ ist visuell und semantisch aktiv (`active`, `aria-selected="true"`), ohne zusätzliche HTTP-Requests und ohne neue CSP-Verletzungen in der Browser-Konsole.

2. **Wechsel zwischen Text- und Datei-Ansicht**
   - **Given** eine Einreichung mit Text und Datei existiert  
   - **When** die Lehrkraft zwischen den Tabs „Text“ und „Datei“ hin- und herklickt  
   - **Then** wird jeweils genau das passende Panel sichtbar (`hidden`-Attribut konsistent), und nur der aktuell gewählte Tab trägt den aktiven Zustand.

3. **Auswertung und Rückmeldung als separate Tabs**
   - **Given** eine Einreichung besitzt sowohl `feedback_md` als auch ein `analysis_json` mit Kriterienauswertung  
   - **When** die Lehrkraft die Live-Detailansicht für diese Einreichung öffnet  
   - **Then** ist zunächst der Tab „Text“ aktiv, und die Tabs „Auswertung“ und „Rückmeldung“ stehen in dieser Reihenfolge zur Auswahl; ihre Inhalte werden jeweils in separaten Panels dargestellt.

### Edge Cases und Fehlerszenarien

4. **Keine Einreichung vorhanden**
   - **Given** eine Zelle ohne Einreichung (kein `has_submission`) wird angeklickt  
   - **When** die Lehrkraft die Detailansicht öffnet  
   - **Then** zeigt das Detail-Panel eine „Keine Einreichung vorhanden“-Karte ohne Tabs, und das SSR-Fragment enthält kein Inline-`<script>`.

5. **Kein Detail ausgewählt**
   - **Given** die Lehrkraft öffnet „Unterricht – Live“, ohne eine Zelle anzuklicken  
   - **When** die Seite geladen ist  
   - **Then** steht im Detailbereich ein Hinweis „Bitte Zelle wählen…“ ohne Tabs und ohne Tab-JS.

6. **Unberechtigter Zugriff**
   - **Given** eine Nutzerin ist nicht eingeloggt oder besitzt keine Teacher-Rolle für den Kurs  
   - **When** sie versucht, die Detail-Route `/teaching/.../live/detail` aufzurufen  
   - **Then** wird sie wie bisher auf die Login-Seite bzw. Startseite umgeleitet; es werden keine Detail-Tabs ausgeliefert.

7. **Mehrere HTMX-Updates**
   - **Given** HTMX lädt nacheinander mehrere Detail-Fragmente in `#live-detail` (z. B. durch Klick auf unterschiedliche Zellen)  
   - **When** die Lehrkraft jeweils auf die Tabs in den nachgeladenen Detail-Ansichten klickt  
   - **Then** funktionieren die Tabs in jedem neuen Fragment korrekt, ohne doppelte Event-Handler oder verwaiste Zustände.

8. **Dev-Umgebung mit lockerer CSP**
   - **Given** die Anwendung läuft in einer Dev- oder Testumgebung, in der `script-src 'self' 'unsafe-inline'` aktiv ist  
   - **When** dieselben Flows wie in Prod ausgeführt werden  
   - **Then** verhält sich die UI identisch (Tabs funktionieren), ohne dass das System von Inline-Skripten abhängig ist.

## Technische Analyse (Ist-Zustand)

### SSR-Partial und Tabs

- Route `GET /teaching/courses/{course_id}/units/{unit_id}/live/detail` (`teaching_unit_live_detail_partial` in `backend/web/main.py`)  
  - prüft Authentifizierung und Teacher-Rolle,  
  - ruft intern den JSON-Endpunkt `/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest` auf,  
  - rendert eine Card mit:
    - Titel `Einreichung von {Name}`  
    - Metadaten `Typ: {kind} · erstellt: {created_at}`  
    - Tabs `("text","Text")`, optional `("file","Datei")`, `("analysis","Auswertung")`, `("feedback","Rückmeldung")`
    - Panels mit `data-panel="text|file|analysis|feedback"` und `role="tabpanel"`, `hidden`-Attribut je nach aktivem Tab.

- Am Ende des Fragments wird ein Inline-`<script>` angehängt, das:
  - über `document.currentScript.closest('.card')` die zugehörige Card findet,  
  - `buttons = card.querySelectorAll('[data-view-tab]')` und `panels = card.querySelectorAll('[data-panel]')` selektiert,  
  - für jeden Button einen Click-Handler registriert, der:
    - `active`-Klasse und `aria-selected` auf den Tabs pflegt,  
    - `hidden`-Attribut der Panels passend setzt.

### HTMX-Einbettung

- Die Lehrkraft-Ansicht `GET /teaching/courses/{course_id}/units/{unit_id}/live` (ebenfalls in `backend/web/main.py`) rendert:
  - die Live-Matrix (Tabelle) und  
  - darunter `<div id="live-detail"></div>` als Zielcontainer für das Detail-Fragment.
- Jede Matrix-Zelle (`<td>`) für eine vorhandene Einreichung besitzt:
  - `hx-get="/teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…"`,  
  - `hx-target="#live-detail"`,  
  - `hx-swap="innerHTML"`.
- Klick auf eine Zelle:
  - HTMX lädt das SSR-Fragment nach,  
  - ersetzt den Inhalt von `#live-detail` durch das neue HTML inklusive Inline-`<script>`.

### CSP-Konfiguration

- In der `security_headers`-Middleware in `backend/web/main.py` wird eine CSP gesetzt:
  - **Prod (`SETTINGS.environment == "prod"`):**  
    `default-src 'self'; script-src 'self'; style-src 'self'; …`  
    → keine Inline-Skripte erlaubt.
  - **Nicht-Prod (Dev/Test):**  
    `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; …`  
    → Inline-Skripte und Inline-Styles sind erlaubt.
- Weitere Inline-Patterns (z. B. `notification.style.cssText = "..."` in `gustav.js`) erzeugen zusätzliche CSP-Warnungen, sind aber nicht direkt für dieses Ticket verantwortlich.

### Frontend-Initialisierung (`gustav.js`)

- Das zentrale JS-Modul `backend/web/static/js/gustav.js` initialisiert:
  - Theme, Sidebar, Keyboard-Shortcuts, Upload-Progress, File-Preview, etc.  
  - HTMX-Hooks in `initHTMX()`:
    - `htmx:afterSwap`, `htmx:oobAfterSwap`, `htmx:afterSettle` für Sidebar/Theme-Reinitialisierung,  
    - Fehler-Handling und Notifications.
- Es gibt **noch keine** zentrale, CSP-sichere Initialisierung für die Teaching-Live-Tabs:
  - keine Funktion `initTeachingLiveTabs`,  
  - keine Event-Delegation für `[data-view-tab]`-Buttons.
- Stattdessen liegt die Tab-Logik ausschließlich im Inline-`<script>` des SSR-Partials.

## Geplante Lösung

Ziel: Die Teaching-Live-Tabs in Prod funktionsfähig machen, **ohne** die CSP zu schwächen und ohne das API- oder DB-Schema zu ändern.

### 1. API- und DB-Impact

- Der bestehende JSON-Endpunkt für die „latest submission“ bleibt unverändert.  
- `api/openapi.yml` muss für dieses Ticket **nicht** geändert werden, da:
  - keine neuen Felder im Teaching-Detail-Response benötigt werden,  
  - keine zusätzlichen Endpunkte oder Parameter eingeführt werden.
- Es sind keine Supabase-/PostgreSQL-Migrationen nötig; das Schema bleibt unverändert.

### 2. Inline-Skript im SSR-Partial entfernen

- In `backend/web/main.py`, Funktion `teaching_unit_live_detail_partial`:
  - das Inline-`<script>` am Ende der Tabs entfernen,  
  - die HTML-Struktur der Tabs (`tab-btn`, `tab-panel`, `data-view-tab`, `data-panel`, `hidden`, `aria-selected`) unverändert lassen.
- Das Fragment wird damit CSP-konform (keine Inline-Skripte mehr), bleibt aber über `data-*`-Attribute „hookbar“ für die zentrale JS-Initialisierung.

### 3. Tab-Initialisierung nach `gustav.js` verlagern

- In `backend/web/static/js/gustav.js`:
  - neue Methode `initTeachingLiveTabs(root)` einführen, die:
    - in `root` (oder `document`) den relevanten Container findet (z. B. `#live-detail`),  
    - alle `[data-view-tab]`-Buttons und `[data-panel]`-Panels selektiert,  
    - Click-Handler registriert, die:
      - genau einen Tab als aktiv markieren (`classList.toggle('active')`, `aria-selected="true"/"false"`),  
      - Panels auf Basis von `data-panel` zeigen/verstecken (`hidden = !on`).
  - die Methode so implementieren, dass:
    - sie mehrfach aufgerufen werden kann, ohne Event-Handler zu duplizieren (z. B. durch erneutes Binden nur im jeweiligen Container oder durch Delegation),  
    - sie auch mit nachgeladenen HTMX-Fragmente funktioniert.

- Integration in `initHTMX()`:
  - im bestehenden Listener für `htmx:afterSwap`:
    - nach den Sidebar-/Theme-Initialisierungen zusätzlich  
      `this.initTeachingLiveTabs(evt.target || document);` aufrufen.
  - optional: beim initialen `init()` einmal `initTeachingLiveTabs(document)` aufrufen, um den Fall abzusichern, dass die Detail-Tabs bereits im ersten SSR-Response vorhanden sind.

### 4. Teststrategie (TDD – Red-Green-Refactor)

1. **Backend-SSR-Tests erweitern (Red)**
   - In `backend/tests/test_teaching_live_detail_ssr.py`:
     - neuen Testfall ergänzen, der für einen Multi-Tab-Fall prüft:
       - `tab-btn`-Buttons und `tab-panel`-Container sind vorhanden,  
       - das gerenderte HTML **kein** `<script>`-Tag im Detail-Fragment enthält (kein Inline-JS in diesem Partial).
     - ergänzend: Tests zur Reihenfolge und ARIA-Markierung der Tabs (insbesondere, dass „Text“ initial aktiv ist).

2. **Inline-Skript entfernen (Green Schritt 1)**
   - Minimaländerung im SSR-Partial, bis der neue Test grün ist:
     - nur das Inline-Skript entfernen, ohne sonstige Logik anzupassen.

3. **JS-Initialisierung implementieren (Green Schritt 2)**
   - `initTeachingLiveTabs(root)` in `gustav.js` implementieren und in `initHTMX()` einhängen.  
   - Manuelle Tests in Dev:
     - „Unterricht – Live“ öffnen, Zelle anklicken, Tabs „Text“/„Datei“/„Auswertung“/„Rückmeldung“ durchklicken.  
   - Optional: später E2E-/JS-Tests (z. B. Playwright oder DOM-Tests) ergänzen, die Click → Panel-Wechsel verifizieren.

4. **Refactor & Dokumentation**
   - Code im Sinne der Projektprinzipien überprüfen:
     - klare Funktionstrennung, keine N+1-Abfragen, keine RLS-Verstöße,  
     - aussagekräftige Docstrings/Kommentare für Lernende („Warum gibt es `initTeachingLiveTabs`?“),  
     - ggf. weitere Inline-Patterns als Follow-up-Tickets für CSP-Härtung markieren (Notifications, Inline-Styles).

## Risiken und Grenzen des Tickets

- Änderungsschwerpunkt liegt im UI-/SSR-Bereich:
  - SSR-Partial `teaching_unit_live_detail_partial` (Entfernen des Inline-Skripts),  
  - Frontend-Script `gustav.js` (neue Tab-Initialisierung und HTMX-Integration).
- Keine Änderungen an API-Verträgen oder Datenbank-Schema → geringes Risiko für Backend-Regressions.
- Haupt-Risiko:
  - mögliche UI-Regressions in den Tabs (z. B. bei sehr vielen schnellen HTMX-Updates), falls die Event-Delegation oder Reinitialisierung fehlerhaft umgesetzt wird.

## Offene Fragen

1. **Ort der Tab-Initialisierung**
   - Soll die Tab-Initialisierung ausschließlich über `htmx:afterSwap` erfolgen, oder zusätzlich beim initialen `init()` für SSR-vorhandene Inhalte?
2. **Generelles CSP-Review**
   - Soll ein separates Ticket für die Bereinigung weiterer CSP-Verstöße (Notifications, Inline-Styles, ältere Inline-Skripte) angelegt werden?
3. **Langfristige Tests**
   - Sollen mittelfristig E2E-/UI-Tests (z. B. Playwright) für zentrale UI-Flows wie Teaching-Live-Tabs eingeführt werden, um CSP-bezogene Regressions frühzeitig zu erkennen?

