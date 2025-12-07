# Ticket: Teaching-Live-Detail-Tabs reagieren in Prod nicht (CSP vs. Inline-JS)

## Problem
- In der „Unterricht – Live“-Ansicht können Lehrkräfte in Prod nicht zwischen den neuen Detail-Tabs „Text“, „Datei“, „Auswertung“ und „Rückmeldung“ wechseln.
- Beim Klick auf die Tab-Buttons passiert im Browser sichtbar nichts:
  - kein Tab-Wechsel,
  - keine Fehlermeldung in der UI,
  - keine zusätzlichen Netzwerk-Requests (F12 → Netzwerk bleibt leer).
- Im Dev-System (lokal, ohne strikte Content Security Policy) funktioniert derselbe Flow erwartungsgemäß.

## Umgebung
- Prod-Domain: `https://app.gustav-lernplattform.de` (Caddy/Keycloak/Supabase/Ollama, Stand nach PR #52 vom 2025-12-04).
- Code-Basis:
  - `origin/master` @ `826784b` („Merge pull request #52 … Teaching Live: sichere Detail-Tabs“).
  - `ops/prod-local` enthält `master` + lokale Deploy-Anpassungen, wurde nach `supabase migration up`, `docker compose build`, `docker compose up -d` ausgerollt.
- Browser-Konsole (F12 → Konsole) in Prod zeigt mehrfach CSP-Warnungen:
  - `Content-Security-Policy: Die Einstellungen der Seite haben die Ausführung eines Inline-Skripts (script-src-elem) blockiert, da es gegen folgende Direktive verstößt: "script-src 'self'" …`
  - ähnlich für Inline-Styles (style-src-attr/-elem) und weitere Inline-Snippets.

## Reproduktion (Prod)
1. Als Lehrkraft in Prod unter `https://app.gustav-lernplattform.de` einloggen.
2. In einen Kurs mit mindestens einer Lerneinheit und Aufgaben gehen.
3. „Unterricht – Live“ öffnen und eine Einheit auswählen, für die bereits Schüler-Einreichungen vorliegen.
4. In der Live-Matrix eine Zelle mit „✅“ anklicken:
   - Erwartung: Detail-Pane unter der Matrix lädt (das passiert korrekt).
   - HTML im Detail-Pane enthält die Tab-Buttons (Text/Datei/Auswertung/Rückmeldung).
5. Jetzt einen der Tabs anklicken (z. B. „Datei“ oder „Auswertung“).

Beobachtung:
- Der sichtbare Inhalt unterhalb der Tabs ändert sich nicht.
- Es werden keine neuen Requests im Netzwerk-Tab ausgelöst (der Tab-Wechsel ist rein clientseitig, aber die JS-Logik läuft nicht).
- In der Konsole erscheinen CSP-Warnungen zu geblockten Inline-Skripten.

## Erwartetes Verhalten
- Nach dem Klick auf einen Tab:
  - Der aktive Tab-Button erhält den aktiven Zustand (CSS-Klasse `active`, `aria-selected="true"`), die anderen werden visuell und semantisch deaktiviert.
  - Das zugehörige Panel (`data-panel="text|file|analysis|feedback"`) wird sichtbar, alle anderen Panels werden per `hidden` ausgeblendet.
  - Es sind keine zusätzlichen HTTP-Requests erforderlich; der Wechsel ist rein clientseitig.
- Dieses Verhalten funktioniert bereits so im Dev-System und sollte in Prod identisch sein – ohne die bestehende CSP zu schwächen.

## Analyse / Root Cause
- Die SSR-Partial-Route `teaching_unit_live_detail_partial` in `backend/web/main.py` rendert das Detail-Pane und hängt am Ende ein Inline-`<script>` an, das die Tab-Logik initialisiert:
  - Buttons: `data-view-tab="text|file|analysis|feedback"` (Klasse `tab-btn`).
  - Panels: `data-panel="text|file|analysis|feedback"` (Klasse `tab-panel`, `hidden`-Attribut).
  - Inline-JS (vereinfacht):  
    ```js
    (function(){
      const card = document.currentScript.closest('.card');
      if (!card) return;
      const buttons = card.querySelectorAll('[data-view-tab]');
      const panels = card.querySelectorAll('[data-panel]');
      buttons.forEach(btn => btn.addEventListener('click', () => { /* active toggling + hidden */ }));
    })();
    ```
  - Der Code verlässt sich auf `document.currentScript`, um die richtige Karte zu finden.
- Dieses Fragment wird via HTMX geladen:
  - Die Matrix-Zelle besitzt `hx-get="/teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…"` und `hx-target="#live-detail"`.
  - HTMX lädt das SSR-Fragment und ersetzt den Inhalt von `#live-detail` (`hx-swap="innerHTML"`).
- In Prod erzwingt die CSP u. a. `script-src 'self'` ohne `'unsafe-inline'`, `nonce` oder `sha256`-Hash für dieses Script:
  - Der Browser rendert das HTML, blockiert aber die Ausführung des Inline-`<script>` im Fragment (siehe CSP-Warnungen in der Konsole).
  - Folge: Es gibt keine Click-Handler auf den Tab-Buttons; das HTML bleibt statisch.
- Im Dev-System (lokal) läuft die gleiche Logik, weil dort entweder keine CSP oder eine lockere Variante aktiv ist, die Inline-Skripte zulässt.
- Zusätzliche CSP-Warnungen zu Inline-Styles (z. B. in `gustav.js` bei `notification.style.cssText = "…"`) deuten darauf hin, dass generell noch weitere Stellen nicht CSP-sicher sind; das konkrete Prod-Bug-Symptom betrifft hier aber zuerst die Teaching-Live-Tabs.

## Vorschlag (Implementierungsrichtung)
Ziel: Tabs in Prod funktionsfähig machen, **ohne die CSP aufzuweichen** (kein `'unsafe-inline'`, kein Aufbohren von `script-src`).

1. **Inline-Skript aus dem SSR-Partial entfernen**
   - In `backend/web/main.py` (Route `teaching_unit_live_detail_partial`) das Inline-`<script>…</script>` nicht mehr ausgeben.
   - HTML-Struktur mit `data-view-tab` und `data-panel` wie bisher beibehalten, damit die Tab-Logik an den bestehenden Hooks aufsetzen kann.

2. **Tab-Initialisierung nach `gustav.js` verlagern**
   - In `backend/web/static/js/gustav.js` eine CSP-kompatible Initialisierung ergänzen, z. B.:
     - Entweder global in `init()` oder spezifisch in `initHTMX()` als Reaktion auf `htmx:afterSwap`:
       ```js
       initTeachingLiveTabs(root) {
         const container = (root || document).querySelector('#live-detail');
         if (!container) return;
         const buttons = container.querySelectorAll('[data-view-tab]');
         const panels = container.querySelectorAll('[data-panel]');
         buttons.forEach((btn) => {
           btn.addEventListener('click', () => {
             const tgt = btn.getAttribute('data-view-tab');
             buttons.forEach((b) => {
               const on = b === btn;
               b.classList.toggle('active', on);
               b.setAttribute('aria-selected', on ? 'true' : 'false');
             });
             panels.forEach((p) => {
               const on = p.getAttribute('data-panel') === tgt;
               p.hidden = !on;
             });
           });
         });
       }
       ```
     - Aufruf z. B. in `initHTMX()`:
       ```js
       document.body.addEventListener('htmx:afterSwap', (evt) => {
         this.initTeachingLiveTabs(evt.target || document);
         // bestehende init-Calls (Theme, Sidebar, Gestures, …)
       });
       ```
   - Wichtig: Event-Listener über Delegation oder erneute Initialisierung nach jedem HTMX-Swap setzen, damit Tabs auch nach nachgeladenen Details und Matrix-Updates funktionieren.

3. **Tests ergänzen/anpassen**
   - Bestehende SSR-Tests (`backend/tests/test_teaching_live_detail_ssr.py`) prüfen aktuell das HTML und teilweise das Vorhandensein von `tab-btn`, aber nicht das tatsächliche Tab-Verhalten im Browser.
   - Ergänzen:
     - E2E-/UI-Test (z. B. Playwright, falls vorhanden) oder minimaler JS-Unit-Test, der sicherstellt, dass die neue `initTeachingLiveTabs`-Logik bei einem Klick die Panels konsistent toggelt.
     - Optional: Dev-Setup mit CSP-Headern (Lokal-Caddy oder Test-Server) so konfigurieren, dass Inline-Skripte ebenfalls geblockt werden, damit solche Bugs frühzeitig auffallen.

4. **Langfristig CSP-Härtung durchziehen**
   - Das Ticket sollte zumindest dokumentieren, dass auch:
     - Inline-Styles in `gustav.js` (z. B. `notification.style.cssText = "…"`) und
     - weitere Inline-Skripte aus älteren Teilen des Frontends
   - nicht CSP-sicher sind und perspektivisch in externe Styles/JS ausgelagert werden sollten.
   - Scope dieses Tickets: funktional minimaler Fix für die Teaching-Live-Detail-Tabs; ob ein eigenes „CSP-Aufräumticket“ erstellt wird (für Notifications, Tooltips etc.), kann das Team entscheiden.

## Risiken / Scope
- Änderung betrifft primär:
  - SSR-Fragment `teaching_unit_live_detail_partial` (Entfernen des Inline-Scripts).
  - Client-Script `gustav.js` (neue Tab-Initialisierung).
- Keine Änderung an API-Verträgen oder DB-Schema (Migration ist bereits in Prod ausgerollt).
- CSP bleibt unverändert streng (`script-src 'self'`), d. h. das Risiko liegt hauptsächlich in potentiellen Regressions im Tabs-UI, falls die neue JS-Lösung fehlerhaft ist.

## Offene Fragen
- Soll im Zuge dieser Änderung ein generelles CSP-Review des Frontends angestoßen werden (Notifications, Tooltips, weitere Inline-Styles / -Scripts)?
- Gibt es Präferenzen für den Ort der Tab-Initialisierung (global in `init()` vs. gezielte Reaktion auf `htmx:afterSwap`), um die JS-Layer möglichst einheitlich zu halten?

