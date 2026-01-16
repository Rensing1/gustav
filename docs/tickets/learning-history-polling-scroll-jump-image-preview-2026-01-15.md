# Ticket: Schüler-Ansicht springt beim Auto-Refresh während Bild-Analyse nach oben (History-Polling rendert Preview neu)

Status: Open

## Problem
- Wenn Schüler:innen eine Aufgabenlösung als **Bild** (oder PDF) einreichen, läuft die Auswertung asynchron.
- Während der Status **`analysis_status ∈ {pending, extracted}`** ist, wird in der Schüler-UI ein Hinweis angezeigt: „Analyse läuft … wir aktualisieren gleich.“
- In dieser Phase wird die **History-Ansicht automatisch alle 2 Sekunden aktualisiert**.
- Beobachtetes UX-Problem: Das hochgeladene Bild wird bei jedem Poll **neu gerendert/neu geladen** und beim Versuch nach unten zu scrollen, wird man **immer wieder nach oben** (zur History bzw. zum Bild) „zurückgesetzt“.

Impact:
- Schüler:innen können während der laufenden Analyse kaum im Verlauf lesen/scrollen.
- Wirkt wie „Seite lädt ständig neu“, obwohl technisch „nur“ ein Fragment getauscht wird.

## Reproduktion
1. Als Schüler:in eine Aufgabe öffnen (Unit-Seite).
2. Lösung als **Upload (JPG/PNG)** abgeben.
3. History-Verlauf der Aufgabe ist sichtbar (durch `show_history_for=...` oder durch das initiale Laden des History-Fragments).
4. Während „Analyse läuft …“ angezeigt wird: nach unten scrollen.

Beobachtung:
- Alle ~2 Sekunden wird der History-Block neu gerendert.
- Die Seite springt zurück nach oben.

## Erwartetes Verhalten
- Polling soll (wenn nötig) **nur den Analyse-/Feedback-Status** aktualisieren.
- Scroll-Position darf beim Auto-Refresh nicht „kaputtgehen“.
- Das Preview des hochgeladenen Bildes soll **nicht alle 2 Sekunden neu geladen** werden.

## Technischer Kontext (Ist-Zustand)
### 1) Trigger: `analysis_status` aktiviert HTMX-Polling
- In `backend/web/main.py` entscheidet `_is_analysis_in_progress()` (`pending`/`extracted`), ob ein History-Fragment auto-pollt.
- Wenn in progress, rendert die UI ein `<section class="task-panel__history">` mit:
  - `hx-get="/learning/courses/{course_id}/tasks/{task_id}/history"`
  - `hx-trigger="load, every 2s"` bzw. `hx-trigger="every 2s"`
  - `hx-swap="outerHTML"`
  - und zeigt den Spinner-Hinweis aus `_render_analysis_in_progress_hint()` („Analyse läuft …“).

Relevante Stellen:
- Spinner-Hinweis: `backend/web/main.py` → `_render_analysis_in_progress_hint()`
- Status-Check: `backend/web/main.py` → `_is_analysis_in_progress()`
- Polling-HTML im Unit-Render: `backend/web/main.py` (TaskCard History Placeholder)
- Polling-HTML im Fragment-Endpunkt: `backend/web/main.py` → `learning_task_history_fragment`
- Tests, die Polling erwarten: `backend/tests/test_learning_ui_auto_refresh.py`

### 2) Ursache für „Bild rendert neu“: Signed URL ändert sich bei jedem Poll
- Das History-Fragment rendert das Preview-HTML im History-Entry:
  - `backend/web/main.py` → `_build_history_entry_from_record()` → `<img class="submission-preview" src="{file_url}">`
- `file_url` wird serverseitig per Presign erzeugt:
  - `backend/web/main.py` → `_enrich_submission_records_with_file_urls()` → `presign_download(...)`
  - `backend/teaching/storage_supabase.py` → `presign_download()` generiert eine Signed URL mit Zeit/Token-Komponenten.
- Da bei **jedem Poll** ein neues SSR-Fragment gerendert wird, wird der Signed-Download-Link typischerweise **neu** erstellt → `img.src` ist bei jedem Swap anders → Browser lädt das Bild wieder.

### 3) Warum springt Scroll nach oben?
Wahrscheinliche Mechanik (kombiniert):
- `hx-swap="outerHTML"` ersetzt das gesamte History-Element im DOM (inkl. `<img>`), nicht nur inneres Markup.
- Durch wechselnde `img.src` lädt der Browser das Bild erneut; zusammen mit fehlender „Platzreservierung“ kann das Layout bei jedem Poll stark verschieben.
- Diese Layout-Shifts interagieren ungünstig mit Browser-Scroll-Anchoring: der Viewport „klebt“ am oberen Bereich des ersetzten Blocks, wodurch es wie ein Reset nach oben wirkt.

Mitigations im aktuellen CSS sind begrenzt:
- `.submission-preview` setzt `max-width: 100%`, aber reserviert keine stabile Höhe/aspect-ratio (`backend/web/static/css/gustav.css`).

## Root Cause (zusammengefasst)
Das History-Fragment pollt im Pending-Zustand alle 2 Sekunden und ersetzt sich komplett (`outerHTML`), inklusive Bild-Preview. Gleichzeitig ändert sich der Signed-URL-`src` bei jedem Poll. Das führt zu wiederholtem Neuladen + Layout-Shift → Scroll „springt“.

## Fix-Optionen (Design-Richtung)
1. **Polling-Granularität reduzieren (präferiert)**
   - Während `pending/extracted` nur den „Status/Feedback“-Teil pollen (z. B. separater Endpoint oder `hx-select`/Teilfragment), aber das Preview-Image in einem stabilen DOM-Knoten lassen.
2. **Stabile Preview-URL während Polling**
   - Signed URL nicht in jedem Poll neu ausgeben (Caching pro Submission für ein Zeitfenster) oder über einen stabilen App-Endpunkt ausliefern, der serverseitig (auth) auf eine presigned URL/streaming mappt.
3. **Layout-Shift minimieren (nur Mitigation)**
   - `width`/`height` Attribute oder `aspect-ratio`/placeholder für `.submission-preview`, damit beim Neuladen weniger Sprung entsteht.
4. **Polling-Pause bei User-Interaktion**
   - Polling pausieren, wenn Nutzer:in aktiv scrollt/History interagiert, und nach X Sekunden Inaktivität fortsetzen (komplexer, eher zweite Iteration).

## Akzeptanzkriterien
- Während „Analyse läuft …“ kann man nach unten scrollen, ohne dass die Seite wieder nach oben springt.
- Das Preview-Bild flackert/relädt nicht mehr alle 2 Sekunden.
- Polling endet weiterhin automatisch, sobald `analysis_status` nicht mehr `pending/extracted` ist.
- Keine Security-Regression: Upload-Artefakte bleiben privat; Zugriff bleibt an Auth/Membership gebunden.

