# Plan: Inline-Preview für Datei-Materialien (modularer Viewer)

Ziel: Lehrkräfte sollen auf der Seite „Material bearbeiten“ (und perspektivisch an anderen Stellen) hochgeladene Datei-Materialien direkt eingebettet sehen, statt nur einen „Download anzeigen“-Link zu bekommen, der einen neuen Tab öffnet. Die Einbettung soll modular und wiederverwendbar sein (z. B. später in Schüler-Ansichten oder im Dashboard).

## User Story

Als Lehrkraft möchte ich beim Bearbeiten eines Datei-Materials die Datei direkt auf der Seite sehen können (z. B. PDF im Viewer, Bild inline), damit ich schnell prüfen kann, ob ich die richtige Datei hochgeladen habe – ohne einen neuen Tab öffnen oder Downloads verwalten zu müssen.

## BDD-Szenarien (Given-When-Then)

1. **Happy Path – PDF-Material**
   - Given ich bin als Lehrkraft angemeldet und öffne die Seite „Material bearbeiten“ für ein Datei-Material vom Typ `application/pdf`,
   - When die Seite geladen ist,
   - Then sehe ich im Kartenbereich oberhalb des Formulars eine eingebettete PDF-Vorschau (z. B. `<iframe>`/`<embed>`), und **kein** Button „Download anzeigen“ mehr.

2. **Happy Path – Bild-Material (PNG/JPEG)**
   - Given ich bin als Lehrkraft angemeldet und öffne ein Datei-Material vom Typ `image/png` oder `image/jpeg`,
   - When die Seite geladen ist,
   - Then wird das Bild direkt auf der Seite angezeigt (z. B. `<img>` mit begrenzter Maximalhöhe) und kein separater Download-Button.

3. **Fallback – Unbekanntes/anderes Format**
   - Given ich öffne ein Datei-Material mit einem MIME-Typ, den wir nicht explizit einbetten (z. B. `application/octet-stream`),
   - When die Seite geladen ist,
   - Then erhalte ich weiterhin einen einfachen Link „Download“ (oder äquivalenten Fallback), weil keine sichere Inline-Preview möglich ist.

4. **Fehler – Kein Download-URL verfügbar**
   - Given die API `/api/teaching/…/download-url` liefert einen Fehler (z. B. 404 oder 503) oder kein `url`-Feld,
   - When die Seite „Material bearbeiten“ geladen wird,
   - Then erscheint keine zerstörte Einbettung; stattdessen sehe ich einen neutralen Hinweis (oder gar nichts) und mindestens das Formular bleibt nutzbar.

5. **Sicherheit – Cache & Autorisierung**
   - Given ich öffne die Material-Bearbeiten-Seite,
   - When ich eine Inline-Preview sehe,
   - Then bleibt das API-Verhalten unverändert:
     - Download-URL wird weiterhin mit `Cache-Control: private, no-store` geliefert,
     - Die Sichtbarkeit ist weiterhin von Lehrkraft-Rollen und Ownership abhängig
     - Es gibt keinen öffentlichen, dauerhaft eingebetteten Link außerhalb des autorisierten Kontextes.

6. **Wiederverwendbarkeit – Modularer Viewer**
   - Given es existiert eine generische Komponente „FilePreview“,
   - When eine andere Seite (z. B. Schüler-Ansicht eines Materials oder ein Dashboard) ein Datei-Material anzeigt,
   - Then kann diese Komponente mit `download_url` + `mime_type` wiederverwendet werden, ohne den Viewer jedes Mal neu zu implementieren.

7. **Interaktiver Zoom (Variante 2 – Zoom-Toggle)**
   - Given eine FilePreview für ein Bild- oder PDF-Material wird angezeigt,
   - When ich als Nutzer (Lehrkraft oder Schüler) auf den Preview-Bereich tippe/klicke,
   - Then wechselt die Vorschau in einen „vergrößert“-Zustand (größere Maximalhöhe, nahezu Vollbild auf dem iPad),
   - And ein weiterer Klick schaltet die Vorschau wieder zurück auf die kompakte Darstellung.
   - And der Zoom-Zustand wird rein clientseitig über eine CSS-Klasse gesteuert (kein zusätzlicher API-Call, keine neue Route).

## API-Vertrag

- Es wird **keine** neue API-Route eingeführt.
- Wir nutzen weiter die bestehende Route:
  - `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url?disposition=inline`
  - Rückgabe: `{ "url": "<short-lived-url>", ... }` mit `Cache-Control: private, no-store`
- OpenAPI:
  - Der bestehende Eintrag für `…/download-url` bleibt unverändert.
  - Die UI nutzt nur `url` und ggf. `content_type` aus der Antwort; falls `content_type` noch nicht im Payload dokumentiert oder geliefert wird, prüfen wir zunächst den bestehenden Vertrag und nutzen für die Inline-Entscheidung bevorzugt den bekannten `mime_type` aus der Material-API (falls verfügbar).

## Datenbank/Migration

- Keine Schemaänderungen.
- Inline-Preview basiert ausschließlich auf vorhandenen Material- und Storage-Metadaten:
  - `material.kind == "file"`
  - `material.file_mime_type` o. Ä. (exakte Feldnamen werden am Repo/Service geprüft) und der Download-Link aus der bestehenden API.

## Technischer Ansatz (modularer Viewer + Zoom)

- **Datenquelle für MIME-Typ**:
  - `_fetch_material_detail` liefert bereits das vollständige Material-Objekt aus `GET /api/teaching/…/materials`.
  - Wir prüfen im Teaching-API-Vertrag, wie Datei-Materialien strukturiert sind (z. B. Felder wie `file_mime_type`, `file_size_bytes`).
  - `material_detail_page` ruft wie bisher `download-url` mit `disposition=inline` auf, um eine kurzlebige URL zu bekommen.

- **Modularer Renderer (Server-seitig)**:
  - Einführung eines kleinen HTML-Render-Helpers, z. B.:
    - Funktion: `_render_file_preview(url: str, mime: str) -> str`
    - Optional: eigener Component-Typ `FilePreview` unter `backend/web/components`, falls wir den Viewer explizit als Komponente führen wollen.
  - Logik:
    - Wenn `mime.startswith("image/")` → `<figure><img src="…" alt="Datei-Material" …></figure>`.
    - Wenn `mime == "application/pdf"` → `<div class="file-preview file-preview--pdf"><iframe src="…" …></iframe></div>`.
    - Sonst → Fallback-Link `<a href="…" target="_blank" rel="noopener">Download</a>`.
  - KISS: kein Client-Side JS nötig, reine SSR-Komponente, maximal konfiguriert über den MIME-Typ.

- **Einbindung in „Material bearbeiten“**:
  - `_render_material_detail_page_html` erweitert um einen optionalen `mime_type`-Parameter oder liest `material["mime_type"]` direkt.
  - Statt des `<a id="material-download-link" …>Download anzeigen</a>` wird der neue Viewer gerendert:
    - „Download anzeigen“-Button entfällt.
    - Optional: kleiner Text „Vorschau“/„Datei-Ansicht“ als Überschrift.

- **Wiederverwendbarkeit**:
  - Der Renderer `_render_file_preview` wird so entworfen, dass er:
    - nur `url` + `mime` benötigt,
    - keine Page-spezifischen IDs/Labels enthält,
    - von anderen Routen wiederverwendet werden kann (z. B. später in einer Schüler-Detail-Ansicht).
  - Dokumentation im Plan + kurzer Verweis in `docs/references/teaching.md` (optional), wie der Viewer genutzt werden kann.

- **Zoom-Toggle (Variante 2, für Lehrer + Schüler)**:
  - CSS:
    - Basis-Preview (bereits umgesetzt): Bild/PDF mit `max-height` (z. B. 480 px) für iPad-freundliche Standardgröße.
    - Zoom-Zustand: zusätzliche Klasse `file-preview--zoomed` auf dem Wrapper:
      - `file-preview--zoomed .file-preview__image { max-height: 90vh; }`
      - `file-preview--zoomed .file-preview__frame { height: 90vh; }`
  - JS:
    - Erweiterung von `Gustav` um eine kleine Initialisierungsmethode (z. B. `initFilePreviewZoom()`), die:
      - Click/Tap-Events auf `.file-preview` (nur `image/*` und `application/pdf`) abfängt,
      - auf dem jeweiligen Wrapper per `classList.toggle("file-preview--zoomed")` den Zoom-Zustand schaltet.
    - Diese Initialisierung wird sowohl auf den Lehrkraft-Seiten (Material-Detail) als auch auf der Schüler-Unit-Seite aktiv, da beide den gemeinsamen `gustav.js` nutzen.
  - A11y:
    - Der Wrapper bekommt `role="button"` + `tabindex="0"` und ein `aria-label` („Vorschau vergrößern/verkleinern“).
    - Optional (später): Escape-Taste schaltet Zoom zurück, falls der Fokus innerhalb des Previews liegt.

## Tests (Rot-Grün-Refactor)

1. **Pytest-UI-Tests für Material-Detail-Seite (Lehrkraft)**
   - Neuer Test in `backend/tests/test_teaching_entry_detail_ui.py` oder eigenständige Datei, z. B. `test_teaching_material_detail_ui_file_preview.py`:
     - Given ein Datei-Material mit MIME `application/pdf`,
       - When ich `/units/{u}/sections/{s}/materials/{m}` abrufe,
       - Then enthält HTML:
         - einen Container mit z. B. `class="file-preview file-preview--pdf"`,
         - ein `<iframe>` oder `<embed>` mit `src="<download-url>"`,
         - **kein** Element mit `id="material-download-link"`.
     - Für `image/png` / `image/jpeg`:
       - `<img src="<download-url>" …>` im DOM,
       - kein „Download anzeigen“-Button.
     - Zoom-Markup:
       - FilePreview-Wrapper hat CSS-Klassen `file-preview file-preview--image` bzw. `file-preview file-preview--pdf`.
       - Wrapper trägt Attribute für Interaktion (`role="button"`, `tabindex="0"`), sodass Klick/Enter-Events vom JS für den Zoom genutzt werden können.
     - Fallback: Wenn kein `download_url` geliefert wird, gibt es keinen kaputten Viewer (Test prüft z. B., dass weder `<iframe>` noch `<img>` vorhanden sind, aber die Seite 200 zurückgibt).

2. **Pytest-UI-Tests für Schüler-Unit-Seite**
   - Erweiterung von `backend/tests/test_learning_unit_sections_ui_cards_markdown.py`:
     - Given eine Unit mit einem freigegebenen Datei-Material (PDF) und einem Bild-Material (PNG),
       - When der Schüler `/learning/courses/{course_id}/units/{unit_id}` aufruft,
       - Then:
         - Beide Materialien erscheinen als `MaterialCard` mit jeweils einem `file-preview`-Container.
         - Für PDF: `file-preview file-preview--pdf` + `<iframe>`/`<embed>` mit der kurzlebigen Download-URL.
         - Für Bild: `file-preview file-preview--image` + `<img>` mit derselben Download-URL.
         - Die Download-URL stammt aus dem Teaching-Storage-Adapter (Supabase) und ist nicht der rohe `storage_key`.
   - Zoom-Verhalten im HTML:
     - Tests prüfen, dass der Wrapper die Zoom-Klasse (`file-preview--zoomed`) **nicht** initial gesetzt hat (Startzustand kompakt).
     - Optional: ein kleiner JS-naher Test (oder DOM-Snippet-Test) prüft, dass das Hinzufügen von `file-preview--zoomed` die Styles verändert (z. B. via Snapshot oder gezielter CSS-Klasse im Markup, ohne echten Browser).

3. **Service-/API-Tests (bereits vorhanden, Regression)**
   - Die bestehenden Tests in `backend/tests/test_teaching_materials_files_api.py` und `test_supabase_storage_e2e.py` prüfen weiterhin:
     - `download-url`-Route (inkl. `disposition=inline`),
     - korrekte Cache-Control-Header,
     - RLS/Autorisierung.
   - Wir ändern hier nichts am Vertrag; Tests dienen als Regression, um sicherzustellen, dass der Viewer nur auf bereits abgesicherten URLs aufsetzt.

3. **Sicherheitstests (OpenAPI + Headers)**
   - `backend/tests/test_openapi_security_headers.py` enthält bereits Checks für `download-url`.
   - Wir verifizieren, dass diese Tests grün bleiben (keine Header-Änderungen erforderlich); Zoom ist rein clientseitig.

## Umsetzungsschritte

1. **Vertrag & Struktur prüfen**
   - Teaching-API-Dokumentation (`api/openapi.yml`) für Datei-Materialien sichten:
     - Felder für MIME & Größe,
     - bestehende `download-url`-Payload.
   - Verifizieren, dass `_fetch_material_detail` alle nötigen Felder ins UI transportiert.

2. **Tests zuerst schreiben (Rot)**
   - Neue/erweiterte Pytests:
     - Material-Detail-UI:
       - PDF/PNG/JPEG-Preview vorhanden (`iframe`/`img`),
       - „Download anzeigen“-Link nicht mehr vorhanden,
       - Zoom-Markup (`file-preview` mit Interaktionsattributen) vorhanden.
       - Fallback bei fehlender URL.
     - Schüler-Unit-UI:
       - Freigegebene Datei-Materialien erzeugen `file-preview`-Container,
       - HTML enthält keine `file-preview--zoomed`-Klasse initial.

3. **Modularen Viewer implementieren (Grün)**
   - (Bereits umgesetzt) `FilePreview`-Komponente serverseitig verwenden.
   - Sicherstellen, dass sie sowohl in `Material bearbeiten` (Lehrkraft) als auch in der Schüler-Unit-Ansicht genutzt wird.

4. **Zoom-Toggle implementieren (Grün)**
   - `gustav.js` um `initFilePreviewZoom` erweitern:
     - findet alle `.file-preview`-Wrapper mit `data-file-preview="true"` (oder äquivalent),
     - setzt Click/Keydown-Handler (Enter/Space) zum Toggeln der Klasse `file-preview--zoomed`.
   - CSS anpassen:
     - Basishöhe für iPad (z. B. 480 px),
     - Zoom-Höhe bis ca. 90 % der Viewport-Höhe.
   - Sicherstellen, dass diese Initialisierung sowohl auf Lehrer- als auch auf Schülerseiten läuft (globale Initialisierung in `Gustav.init()`).

5. **Refactor & Dokumentation**
   - Code auf KISS/Security prüfen:
     - keine Inline-Skripte, nur SSR-HTML,
     - keine Leaks (keine student/PII in URLs/Logs).
   - Optional:
     - Kurzer Absatz in `docs/references/teaching.md`, wie der Viewer wiederverwendet werden kann.

5. **Regression & Review**
   - `.venv/bin/pytest backend/tests/test_teaching_materials_new_ui.py backend/tests/test_teaching_entry_detail_ui.py backend/tests/test_learning_unit_sections_ui_cards_markdown.py -q`
   - Bei Erfolg: Ready für spätere Wiederverwendung in weiteren Schüler-Ansichten.
