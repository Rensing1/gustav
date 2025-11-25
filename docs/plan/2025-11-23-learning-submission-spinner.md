# Plan: Lernende sehen „Analyse läuft …“-Hinweis bei Pending-Submissions (2025-11-23)

## Kontext & Ziel
- Scope: Schüler-UI beim Einreichen von Aufgaben. Nach POST `/api/learning/.../submissions` bleibt `analysis_status=pending`/`extracted` bis der Worker OCR/Feedback liefert; aktuell nur Erfolgstoast „Erfolgreich eingereicht“ und Polling im Hintergrund, aber kein sichtbarer Hinweis, dass die Auswertung läuft.
- Relevante Stellen:
  - API/Status: `docs/references/learning.md` (Submissions 202 Accepted, Statuswerte `pending|extracted|completed|failed`, Polling via GET /submissions).
  - UI SSR/HTMX: `backend/web/main.py` (TaskCard, History-Placeholder mit `data-pending` + `hx-trigger="every 2s"`), `TaskCard` in `backend/web/components/cards/task.py`.
  - JS: `backend/web/static/js/gustav.js` (Notifications/HTMX), `learning_upload.js` (Upload-Prep). Polling läuft rein mit HTMX; kein Loading-Indikator außer neutralem Text „Lade Verlauf …“.
  - CSS: `backend/web/static/css/gustav.css` (Alerts, Badges; Spinner bislang nicht genutzt, ggf. ergänzen).
- Ziel: Ein kleiner, kontextnaher Hinweis mit Spinner „Analyse läuft …“ soll erscheinen, solange die neueste Submission in `pending`/`extracted` ist. Er verschwindet automatisch, sobald das Polling eine fertige (`completed`/`failed`) Submission lädt. Keine API-Änderung nötig.

## User Story
Als Lernende:r möchte ich nach dem Abschicken einer Abgabe klar sehen, dass die KI gerade meine Lösung verarbeitet, damit ich weiß, dass ich auf das Feedback warten soll.

## BDD-Szenarien (Given-When-Then)
1) Happy Path — Pending Status  
- Given ich reiche eine Aufgabe ein und der API-Response `analysis_status` ist `pending`  
- When das UI die Historie lädt bzw. pollt  
- Then wird im Task-Verlauf ein kleiner Spinner mit dem Text „Analyse läuft … wir aktualisieren gleich.“ angezeigt  
- And der Hinweis verschwindet, sobald `analysis_status` zu `completed` wechselt.

2) PDF Zwischenstatus (`extracted`)  
- Given meine letzte Abgabe ist `extracted` (PDF vor OCR/Feedback)  
- When das UI den Verlauf anzeigt  
- Then derselbe Spinner-Hinweis wird angezeigt, bis der Status `completed` oder `failed` ist.

3) Fehlgeschlagen  
- Given die neueste Abgabe ist `failed`  
- Then kein Spinner wird angezeigt  
- And der vorhandene Fehlerblock („Analyse fehlgeschlagen“) bleibt unverändert.

4) Historie leer / keine Pending  
- Given es gibt keine Submissions oder die neueste ist `completed`  
- Then kein Spinner-Hinweis wird angezeigt.

5) Polling-Fehler (Netzwerk)  
- Given HTMX-Request auf das History-Fragment schlägt fehl  
- Then der Spinner bleibt bestehen, bis ein erfolgreicher Poll den Status liefert  
- And `htmx:responseError` zeigt weiterhin den globalen Error-Toast (bestehendes Verhalten).

## Grober Lösungsansatz
- SSR/Fragment-Änderung: Wenn `_is_analysis_in_progress(latest_status)` true ist, rendert das History-Fragment (`/learning/.../history`) und der Initial-Placeholder einen kompakten Statusblock mit Spinner + Text. Der Block basiert auf `data-pending="true"` und verschwindet, wenn das Polling `data-pending="false"` rendert.
- Platzierung: Im `section.task-panel__history`, oberhalb der History-Einträge (oder im Placeholder statt „Lade Verlauf …“). Barrierefrei mit `role="status"` und `aria-live="polite"`.
- CSS: Kleiner Inline-Spinner (border- oder dot-Animation) in Primärfarbe, dezenter Hintergrund (`--color-bg-overlay`), Text muted. Responsiv, ohne Layout-Sprung.
- Keine Contract-/DB-Änderung: OpenAPI bleibt unverändert; wir nutzen bestehendes `analysis_status` + Polling.

## Tasks / Checks
- [ ] History-Fragment/Placeholder um Statuschip mit Spinner ergänzen, wenn pending/extracted.
- [ ] Kleine Spinner-CSS (falls nicht vorhanden) hinzufügen; ggf. Wiederverwendung vorhandener Alert/Badge-Styles.
- [ ] Accessibility: `role="status"`, `aria-live="polite"`, verständlicher Text.
- [ ] Manuelle Verifikation: Pending-State simulieren (Submission mit `analysis_status=pending`) → Fragment zeigt Spinner; nach Wechsel zu `completed` verschwindet er. HTMX-Error weiterhin via Notification.
- [ ] Tests anpassen/ergänzen: HTML-Fragment-Assertion (pending → enthält Statuschip, completed → nicht). Fokus auf SSR-Fragment, kein JS-Test nötig.

## Offen / Risiken
- Spinner-Implementierung: Falls schon ein globaler Spinner-Utility existiert, wiederverwenden; sonst minimaler CSS-Block hinzufügen.
- Polling-Frequenz bleibt 2s; Hinweis soll nicht flackern, wenn Server langsam antwortet.
- Dark/Light-Themes prüfen (Farben über Tokens halten).

## Spinner-Utility (geplant, wiederverwendbar)
- Kein bestehender Spinner gefunden; wir fügen eine schlanke Utility in `backend/web/static/css/gustav.css` hinzu:
  - Klassen: `.spinner` (inline-flex, border-Spinner mit Keyframes `spin`), Varianten `.spinner--sm|--md|--lg`, optional `.spinner--muted`.
  - Farben: Primär über Tokens (`--color-primary` für aktiven Bogen, `--color-border` für übrige Ringe), respektiert Light/Dark.
  - A11y: `role="status"`/`aria-live="polite"` auf umschließendem Chip, `aria-hidden="true"` auf dem Spinner selbst.
- Statuschip-Stil: `.status-chip` (flex-row, kleiner Overlay-Hintergrund `--color-bg-overlay`, Text muted), `.status-chip__text` für Typografie.
- Verwendung initial im History-Pending-Hinweis, perspektivisch auch für HX-Indikatoren oder Button-Loading.

### Anschauliches Design
- Form: kleiner Kreis mit transparenter Grundlinie und einem gefärbten Segment (border-top in Primärfarbe), rotiert kontinuierlich (500–700ms pro Umdrehung).
- Größe: `--sm` ca. 14px, `--md` ca. 18px; eingesetzt wird `--sm` im Statuschip.
- Einbettung: Spinner links, rechts daneben Text „Analyse läuft … wir aktualisieren gleich.“ auf dezentem Overlay-Hintergrund; wirkt wie ein kompakter Status-Badge.
- Wirkung: dezent, nicht blockierend; inline-height stabil, damit der Task-Verlauf nicht springt; Farben nutzen die bestehenden Token für Lesbarkeit in Light/Dark.
