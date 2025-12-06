# 2025-12-06 – Teaching Live: Auto-Polling für Matrix

Ziel: Die Live-Ansicht auf Einheitenebene (`/teaching/courses/{course_id}/units/{unit_id}/live`) soll sich automatisch aktualisieren, sobald neue Einreichungen eingehen. Die bestehende Summary-/Delta-API ist bereits implementiert; es fehlt die UI-Verdrahtung (Polling + OOB-Updates).

## Ausgangslage

- Backend:
  - JSON-Endpoints existieren bereits:
    - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
    - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
  - SSR-UI-Routen existieren bereits:
    - `GET /teaching/courses/{course_id}/units/{unit_id}/live`
    - `GET /teaching/courses/{course_id}/units/{unit_id}/live/matrix`
    - `GET /teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta`
  - Delta-Route liefert OOB-`<td>`-Fragmente mit `hx-swap-oob="true"` (siehe `backend/web/main.py::teaching_unit_live_matrix_delta_partial`).
  - Tests für Summary/Delta/SSR-Fragment existieren bereits:
    - `backend/tests/test_teaching_live_unit_summary_api.py`
    - `backend/tests/test_teaching_live_unit_delta_api.py`
    - `backend/tests/test_teaching_live_unit_ui_ssr.py`
- UI:
  - Die Live-Seite rendert aktuell eine statische Matrix mit Statuszeile „Letzte Aktualisierung: jetzt“, aber ohne Polling-Attribute (`hx-get`, `hx-trigger`, Cursor).
  - Es gibt noch keine JS-/HTMX-Logik, die `updated_since` verwaltet und zyklisch `…/live/matrix/delta` aufruft.
  - `docs/references/teaching_live.md` und `docs/plan/2025-11-01-teaching-live-section-view.md` beschreiben bereits das gewünschte Polling-Verhalten und die Cursor-Semantik.

## User Story

Als Lehrkraft möchte ich, dass sich die Live-Matrix auf der Seite „Unterricht › Live“ automatisch innerhalb weniger Sekunden nach neuen Schülerabgaben aktualisiert, damit ich während des Unterrichts den Arbeitsfortschritt beobachten kann, ohne die Seite manuell neu laden zu müssen.

## BDD-Szenarien (UI-Perspektive)

### Happy Path – automatische Aktualisierung

- Given ich bin Kurs-Owner und habe die Live-Seite `/teaching/courses/{cid}/units/{uid}/live` geöffnet,
- And die Statusleiste zeigt einen initialen Zeitstempel `data-updated-since=T0`,
- When ein Schüler nach `T0` eine neue Einreichung abgibt,
- And das Polling ruft regelmäßig `GET /teaching/courses/{cid}/units/{uid}/live/matrix/delta?updated_since=T0` auf,
- Then innerhalb weniger Sekunden wird die entsprechende Zelle in der Matrix auf `✅` aktualisiert,
- And die Statusleiste zeigt einen neuen Zeitstempel `T1 > T0` als „Letzte Aktualisierung“.

### Keine Änderungen – 204

- Given die Live-Seite ist geöffnet und `data-updated-since=T0` gesetzt,
- And seit `T0` gab es keine neuen Einreichungen,
- When der Poll `GET …/live/matrix/delta?updated_since=T0` ausgeführt wird,
- Then erhält der Client `204 No Content`,
- And die Matrix bleibt unverändert,
- And die Statusleiste ändert ihren Zeitstempel nicht.

### Mehrere Änderungen – Cursor wird fortgeschrieben

- Given die Live-Seite ist geöffnet mit Cursor `T0`,
- And zwei verschiedene Schüler geben nach `T0` Abgaben zu unterschiedlichen Aufgaben ab,
- When der nächste Poll `GET …/live/matrix/delta?updated_since=T0` ausgeführt wird,
- Then enthält die Antwort OOB-`<td>`-Fragmente für alle geänderten Zellen mit `✅`,
- And die Statusleiste setzt `data-updated-since` auf den maximalen `changed_at`-Wert aus den gelieferten Zellen.

### Verbindungsfehler beim Polling

- Given die Live-Seite ist geöffnet und Polling läuft alle 3–5 Sekunden,
- When der Delta-Request wegen eines Netzwerk- oder Serverfehlers mit 5xx scheitert,
- Then zeigt die Statusleiste einen Hinweis wie „Verbindung unterbrochen“,
- And das Polling versucht im nächsten Intervall automatisch erneut, ohne die Seite neu zu laden.

### Autorisierungsfehler (Session abgelaufen)

- Given die Live-Seite ist geöffnet und Polling läuft,
- And meine Session ist abgelaufen oder ich bin nicht mehr als Lehrer authentifiziert,
- When der Delta-Request mit 401/403 beantwortet wird,
- Then werde ich gemäß bestehender UI-Policy umgeleitet (z.B. Login/Startseite),
- Or die Statusleiste zeigt eine Meldung, dass ich mich neu anmelden muss.

### Initialer Aufruf ohne Aufgaben

- Given die ausgewählte Lerneinheit hat keine Aufgaben,
- When ich die Live-Seite öffne,
- Then sehe ich eine Karte „Keine Aufgaben in dieser Lerneinheit“ statt einer Tabelle,
- And es findet kein Polling der Delta-Route statt (da es keine Zellen gibt).

## Vertrag / OpenAPI / DB

- API-Vertrag:
  - Relevante Endpunkte sind bereits in `api/openapi.yml` definiert:
    - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
    - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
  - Die SSR-Routen (`/teaching/courses/{cid}/units/{uid}/live*`) sind UI-spezifisch und bleiben bewusst außerhalb des OpenAPI-Vertrags.
  - Für diesen Bugfix sind keine Änderungen an `api/openapi.yml` nötig; die UI muss die bestehenden Endpunkte nur wie dokumentiert nutzen (inkl. `updated_since`/EPS-Semantik).
- DB / Migration:
  - Delta-Logik nutzt bestehende Helper (`get_unit_latest_submissions_for_owner(…)`) und `public.learning_submissions`.
  - Keine neuen Spalten/Tabellen erforderlich; „geändert seit“ wird aus vorhandenen Timestamps abgeleitet.
  - Es ist keine neue Supabase/PostgreSQL-Migration geplant; der Fix erfolgt ausschließlich auf UI-/SSR-Ebene.

## Teststrategie (TDD)

Neue bzw. erweiterte Tests in `backend/tests/test_teaching_live_unit_ui_ssr.py`:

1. **`test_live_page_includes_polling_attributes`**
   - Set-up wie `test_live_page_teacher_only_and_renders_table` (Kurs, Einheit, Abschnitt, Aufgabe, Mitglied, Sichtbarkeit).
   - Erwartung:
     - HTML enthält `div id="live-status"` mit Attribut `data-updated-since="…"`.
     - Ein Polling-Element (z.B. `#live-section` oder ein Unter-`div`) besitzt:
       - `hx-get="/teaching/courses/{cid}/units/{uid}/live/matrix/delta"`
       - `hx-trigger="every 3s"` (oder konfiguriertes Intervall).
       - Mechanismus zur Übergabe von `updated_since` (z.B. via `hx-vals` oder URL-Query).

2. **`test_delta_fragment_sets_cursor_via_hx_trigger`**
   - Simulierter Delta-Response mit mindestens einer Zelle (z.B. über existierende API-Tests/Helper).
   - Aufruf von `/teaching/courses/{cid}/units/{uid}/live/matrix/delta?updated_since=T0`.
   - Erwartung:
     - Response enthält OOB-`<td>`-Fragmente wie bisher.
     - Response-Header enthält `HX-Trigger` mit einem JSON-Event, z.B.:
       - `{"liveCursorUpdated": {"cursor": "<max_changed_at_iso>"}}`.

3. **(Optional) JS-nahe Tests**
   - Reines Python/SSR-Testing kann nur die Präsenz von Attributen/Headers prüfen.
   - Das tatsächliche Aktualisieren von `data-updated-since` und der Statuszeile erfolgt im Browser via JS; hier reichen manuelle/integrierte Browser-Tests.

## Geplante Implementierungsschritte

### 1) HTML/SSR: initialen Cursor und Polling-Hook ergänzen

- In `backend/web/main.py::teaching_unit_live_page`:
  - Beim Rendern der Statusleiste einen initialen Cursor setzen, z.B.:
    - `data-updated-since="<now_iso_utc>"` am `div id="live-status"`.
  - Optional den sichtbaren Text „Letzte Aktualisierung: …“ so gestalten, dass er später per JS mit lokaler Uhrzeit überschrieben werden kann.
  - Ein Polling-Element definieren:
    - entweder direkt `section#live-section`,
    - oder ein untergeordnetes `<div id="live-poller">`.
  - Polling-Element mit HTMX-Attributen ausstatten:
    - `hx-get="/teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta"`,
    - `hx-trigger="every 3s"` (oder konfigurierbares Intervall),
    - Übergabe von `updated_since`:
      - z.B. via `hx-vals='{"updated_since": "..."}'`, das später durch JS aktualisiert wird,
      - oder durch JS, das die URL inklusive Query-Parameter setzt.

### 2) SSR-Delta-Route: Cursor im `HX-Trigger` zurückgeben

- In `backend/web/main.py::teaching_unit_live_matrix_delta_partial`:
  - Nach dem Aufruf der JSON-Delta-API:
    - Aus der `cells`-Liste den maximalen `changed_at`-Wert bestimmen (als ISO-String).
  - Response-Header ergänzen:
    - `HX-Trigger: {"liveCursorUpdated": {"cursor": "<max_changed_at_iso>"}}`.
  - Bestehendes Verhalten (OOB-`<td>`-Fragmente, 204 bei keinen Zellen) bleibt unverändert.

### 3) Client-JS: Cursor und Statuszeile verwalten

- In `backend/web/static/js/gustav.js`:
  - Neue Initialisierungsfunktion, z.B. `initTeachingLivePolling()`:
    - Läuft auf DOM-Ready und nach `htmx:afterSwap`/`htmx:oobAfterSwap`.
    - Prüft, ob `#live-section` und `#live-status` existieren.
    - Konfiguriert das Polling-Element:
      - Liest `data-updated-since` aus `#live-status`.
      - Schreibt diesen Wert in `hx-vals` (oder vergleichbare Mechanik) des Polling-Elements, sodass `updated_since` bei jedem Request gesetzt wird.
  - Event-Handler für Cursor-Update:
    - Hört auf das Custom-Event `liveCursorUpdated` (aus `HX-Trigger`):
      - Aktualisiert `data-updated-since` am `#live-status`.
      - Aktualisiert den sichtbaren Text, z.B. „Letzte Aktualisierung: HH:MM:SS“ (lokale Zeit).
      - Aktualisiert die `hx-vals` (oder URL-Konfiguration) des Polling-Elements mit dem neuen Cursor.
  - Fehlerbehandlung:
    - In bestehenden `htmx:responseError`-Handler integrieren:
      - Wenn die Antwort von der Delta-Route kommt und Status 5xx ist:
        - Statusleiste auf „Verbindung unterbrochen“ o.Ä. setzen.
      - Bei 401/403 ggf. auf bestehende Redirect-Mechanismen setzen; falls HTMX keinen Redirect ausführt, Statusleiste auf „Bitte neu anmelden“ setzen.

## Nicht-Ziele dieses Plans

- Keine Änderungen am OpenAPI-Vertrag oder an der DB-Struktur.
- Kein Umstieg auf WebSockets/SSE; Polling via Delta-Endpoint bleibt Standard.
- Keine tiefgehenden Refactorings der bestehenden Live-API/Use-Cases; Fokus liegt auf dem Schließen der UI-Lücke (Polling + Cursor-Verwaltung).

