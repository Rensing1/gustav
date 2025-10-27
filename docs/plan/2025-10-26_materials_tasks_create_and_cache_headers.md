# Plan: Materialien und Aufgaben innerhalb von Abschnitten (Option A) — Cache‑Header ergänzen

Ziel: Lehrkräfte können innerhalb eines Abschnitts Material und Aufgaben anlegen. Materialien und Aufgaben erscheinen getrennt, jeweils mit eigener Reihenfolge. Zusätzlich härten wir die API, indem die Listenendpunkte explizit `Cache-Control: private, no-store` liefern und dies im OpenAPI-Vertrag dokumentiert wird.

## User Story
Als Lehrkraft möchte ich in einem Abschnitt einer Lerneinheit neue Materialien (Markdown oder Datei) und neue Aufgaben anlegen, damit ich den Schülern strukturierte Inhalte und Arbeitsaufträge bereitstellen kann. Die Materialien und Aufgaben sollen getrennt erscheinen und jeweils eindeutig sortiert werden können.

## BDD‑Szenarien (Given‑When‑Then)
- Happy Path (Material anlegen)
  - Given ich bin als Lehrkraft (Autor der Unit) angemeldet und der Abschnitt existiert
  - When ich ein neues Markdown‑Material mit gültigem `title` und `body_md` anlege
  - Then erhalte ich 201 mit dem Material, `position` ist die nächste Zahl, und ein späteres `GET /materials` listet es an letzter Stelle; der Response hat `Cache-Control: private, no-store`.
- Happy Path (Aufgabe anlegen)
  - Given ich bin als Lehrkraft (Autor) und der Abschnitt existiert
  - When ich eine Aufgabe mit `instruction_md` und optionalen Feldern (`criteria`, `hints_md`, `due_at`, `max_attempts`) anlege
  - Then erhalte ich 201 mit der Aufgabe, `position` ist die nächste Zahl, und ein späteres `GET /tasks` listet sie an letzter Stelle; der Response hat `Cache-Control: private, no-store`.
- Edge: Leere/ungültige Felder
  - Given ich bin Autor, Abschnitt existiert
  - When ich ein Material ohne `title` oder ohne `body_md` anlege
  - Then erhalte ich 400 `invalid_title` bzw. `invalid_body_md`.
  - When ich eine Aufgabe ohne `instruction_md` anlege
  - Then erhalte ich 400 `invalid_instruction_md`.
- Fehler: Nicht‑Autor
  - Given ich bin nicht der Autor der Unit
  - When ich Material/Aufgabe anlegen möchte
  - Then erhalte ich 403.
- Fehler: Ungültige Pfadparameter
  - When `unit_id` oder `section_id` kein UUID‑Format haben
  - Then erhalte ich 400 mit `invalid_unit_id` bzw. `invalid_section_id`.
- Edge: Getrennte Reihenfolgen
  - Given ein Abschnitt mit 1 Material und 1 Aufgabe
  - When ich weitere Einträge anlege
  - Then die Material‑Liste und die Aufgaben‑Liste haben jeweils ihre eigene, konsistente `position`‑Sequenz unabhängig voneinander.

## API (OpenAPI‑Ergänzung)
- Dokumentiere für:
  - `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials` (200): Header `Cache-Control: private, no-store`
  - `GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks` (200): Header `Cache-Control: private, no-store`
- Keine Funktionsänderung am Vertrag der Create‑Endpunkte erforderlich.

## Datenbank / Migration
- Keine neuen Migrationen erforderlich. Bereits vorhanden:
  - `public.unit_materials` (Markdown/File, Position, RLS) → `20251022070502_teaching_unit_materials_markdown.sql`, `20251022093725_teaching_materials_file_support.sql`
  - `public.unit_tasks` (Position, RLS) → `20251023061402_teaching_unit_tasks.sql`
  - Upload‑Intents & RLS‑Policies vorhanden.

## TDD
1) Vertrag (OpenAPI) anpassen (Cache‑Header dokumentieren)
2) Failing Tests schreiben:
   - Runtime‑Tests prüfen, dass `GET …/materials` und `GET …/tasks` `Cache-Control: private, no-store` liefern
   - (Optional) OpenAPI‑Test prüft, dass die Header dokumentiert sind
3) Minimalen Code anpassen (Web‑Adapter): Rückgaben der Listenendpunkte mit `Cache-Control` versehen
4) Grün machen, dann kleines Refactoring/Review und Doku‑Comments ergänzen

---

Hinweis auf Bounded Contexts: Trennung zwischen Teaching (Erstellen/Verwalten von Einheiten, Abschnitten, Materialien/Aufgaben) und Learning (Nutzung durch Schüler) bleibt gewahrt (docs/bounded_contexts.md:23). Die getrennte Reihenfolge für Materialien/Aufgaben spiegelt die Aggregat‑Abgrenzung im `Lerneinheit`‑Aggregat wider.

## UI/UX (SSR, konsistent mit „/units“ und „/courses“)

Prinzipien
- SSR + HTMX: Alle Seiten rendern serverseitig HTML und rufen intern ausschließlich die öffentliche Teaching‑API auf (wie bei `/courses`, `/units`).
- KISS & A11y: Einfache, klare Listen mit stabilen Wrapper‑IDs; Drag‑Handle für Reorder plus Fallback‑Buttons für Tastaturbedienung.
- Privacy: Seiten liefern `Cache-Control: private, no-store`.

Seitenfluss (Lehrkraft)
- `/units/{unit_id}` (Abschnitte verwalten)
  - Jede Abschnittskarte enthält eine Aktion „Material & Aufgaben“, die zur Abschnitts‑Detailseite führt: `/units/{unit_id}/sections/{section_id}`.

- `/units/{unit_id}/sections/{section_id}` (Abschnitts‑Detail)
  - Zeigt zwei Listen (Materialien | Aufgaben) und darüber zwei Buttons „+ Material“ und „+ Aufgabe“.
  - Einträge sind klickbar und führen zur jeweiligen Detailseite.
  - Reorder per Drag & Drop (htmx‑sortable); CSRF via `X‑CSRF‑Token`.

- Erstellen
  - `/units/{u}/sections/{s}/materials/new`: Zwei Flows — Markdown‑Text (title, body_md) und Datei‑Upload (Upload‑Intent → Upload → Finalize). CSRF‑Formulare, PRG zurück zur Abschnittsseite.
  - `/units/{u}/sections/{s}/tasks/new`: instruction_md, Kriterien[0..10], hints_md; optional due_at (RFC3339) und max_attempts; PRG zurück zur Abschnittsseite.

- Detailseiten pro Eintrag
  - `/units/{u}/sections/{s}/materials/{m}`: Bearbeiten/Löschen; bei Datei‑Materialien „Download anzeigen“ (presigned URL via API `…/download-url`).
  - `/units/{u}/sections/{s}/tasks/{t}`: Bearbeiten/Löschen (inkl. Kriterien/Hinweise/due_at/max_attempts).

UI‑Routen (HTML; delegieren an JSON‑API)
- GET `/units/{unit_id}/sections/{section_id}` → lädt Unit/Section/Listen via API; Rendert nur Listen + Aktionen; `Cache-Control: private, no-store`.
- GET `/units/{u}/sections/{s}/materials/new` und `/tasks/new` → Erstellen‑Seiten (s. o.).
- POST `/units/{u}/sections/{s}/materials/create|tasks/create` → ruft API, PRG zurück zur Abschnittsseite (bei HTMX optional Partial‑Update).
- POST `/units/{u}/sections/{s}/materials/reorder|tasks/reorder` → ruft API‑Reorder; Fehler werden als Banner gemeldet.
- POST `/units/{u}/sections/{s}/materials/upload-intent` und `/materials/finalize` → 2‑Phasen Datei‑Flow.
- GET `/units/{u}/sections/{s}/materials/{m}` und `/tasks/{t}` → per‑Entry Detailseiten mit Edit/Delete, Datei‑Downloadlink für File‑Materialien.

Listen‑Partials (HTML‑IDs & Reorder)
- Materialien: Wrapper `<section id="material-list-section-{section_id}">` mit innerem `<div class="material-list" hx-ext="sortable" data-reorder-url="…/materials/reorder">` und Items `<div class="card material-card" id="material_{id}">`.
- Aufgaben: Wrapper `<section id="task-list-section-{section_id}">` mit `<div class="task-list" hx-ext="sortable" data-reorder-url="…/tasks/reorder">` und Items `<div class="card task-card" id="task_{id}">`.
- Drag‑Handle Symbol `☰` als Griff; Fallback‑Buttons „Nach oben/Nach unten“ für Tastaturbedienung.

Fehlermapping (geplant)
- 400 → Feldfehler markieren (aria-invalid) und erklärenden Text per aria-describedby anzeigen (z. B. `invalid_title`, `invalid_due_at`).
- 403 → Banner „Keine Berechtigung“ (role="alert"); Link zurück zu `/units`.
- 404 → Banner „Nicht gefunden“ (role="alert"); Link zurück zu `/units`.

Detailseiten für einzelne Einträge
- siehe oben unter „Seitenfluss“ (bereits implementiert)

## Nächste Schritte (Umsetzung)

1) A11y & Fehlermapping
- Banner‑Partial (role="alert"/aria-live) + Feldfehler (aria-invalid, aria-describedby) für Create/Detail‑Formulare (Material/Text, Datei‑Finalize, Task).
- Fokusmanagement nach Fehlersubmit (erstes Fehlerfeld/Banner fokusieren).
- Mapping‑Tabelle (API detail → UI‑Text): `invalid_title`, `invalid_body_md`, `invalid_criteria`, `invalid_due_at`, `invalid_max_attempts`, `mime_not_allowed`, `checksum_mismatch`, `intent_expired`, `forbidden`, `not_found`.
- Tests: Prüfen, dass Fehlermeldungen sichtbar (role="alert") und den Feldern zugeordnet sind.

2) Reorder Tastatur‑Fallback
- Neben dem Drag‑Handle Buttons „↑/↓“ pro Item einblenden (postet neue Reihenfolge).
- Tests: Pfeil‑Buttons erzeugen gültige Reihenfolge; CSRF enforced.

3) Download‑Umschalter (optional)
- „Im Browser anzeigen / Als Datei herunterladen“ (disposition=`inline|attachment`).

4) Komponenten
- Listen‑Partials in `backend/web/components` extrahieren (Wiederverwendung, Tests vereinfachen).

5) Detailseiten pro Eintrag (Material/Aufgabe)
- GET UI‑Routen: `/materials/{material_id}` und `/tasks/{task_id}` (unterhalb des Abschnitts)
- Rendern Vollansichten inkl. Aktionen (Bearbeiten/Entfernen ⇒ späteres PATCH/DELETE via API)
- Cache‑Header: `private, no-store`

6) Tests (TDD)
- OpenAPI: bereits ergänzt (Cache‑Header für Listen)
- Runtime: neue Tests für SSR‑Detailseite (200, Cache‑Header), für UI‑POST (CSRF erzwungen, Fehlerfall‑Mapping minimal)
- Keine E2E‑Uploads im CI: Storage‑Adapter via Fake/Stub wie vorhanden (Supabase‑Adaptertests existieren)

7) Security & A11y
- CSRF‑Token in allen UI‑POSTs; Same‑Origin und `credentials: same-origin` für Fetch
- `Cache-Control: private, no-store` für SSR und JSON
- Tastatur‑Fallback für Reorder („Nach oben/Nach unten“)

## Statusupdate 2025-10-26 (Abends)

- Implementiert (SSR + UI):
  - GET `/units/{unit_id}/sections/{section_id}` mit Zweispalten‑Layout (Materialien | Aufgaben), stabile Wrapper‑IDs:
    - `#material-list-section-{section_id}`
    - `#task-list-section-{section_id}`
    - Seite liefert `Cache-Control: private, no-store`.
  - POST (UI) zum Anlegen und Umordnen:
    - `POST /units/{unit_id}/sections/{section_id}/materials/create`
    - `POST /units/{unit_id}/sections/{section_id}/materials/reorder` (accepts `id=material_<uuid>`)
    - `POST /units/{unit_id}/sections/{section_id}/tasks/create`
    - `POST /units/{unit_id}/sections/{section_id}/tasks/reorder` (accepts `id=task_<uuid>`)
    - Alle POSTs erzwingen CSRF und delegieren an die API.
  - UI-Rework: Hauptseite zeigt nur Listen + Buttons „+ Material“/„+ Aufgabe“. Anlegen erfolgt auf separaten Seiten:
    - GET `/units/{u}/sections/{s}/materials/new` (Text‑Material und Datei‑Upload, beides mit CSRF)
    - GET `/units/{u}/sections/{s}/tasks/new` (Anweisung, 0–10 Kriterien, Hinweise)
  - Tests (pytest): `backend/tests/test_teaching_section_detail_ui.py`, `backend/tests/test_teaching_entry_detail_ui.py`
    - Wrapper + Cache‑Header
    - Create‑Flows via PRG (Material Markdown/Datei, Task mit Kriterien/Hinweisen)
    - Reorder‑Flows (Material/Task) inkl. CSRF‑Negativfall
    - Detailseiten (Edit/Delete) inkl. Datei‑Download

- Offene Punkte (nächste Schritte):
  - A11y & Fehlermapping (Banner/Feldmarkierung, Fokus, Mapping‑Tabelle; s. oben)
  - Tastatur‑Fallback für Reorder (Buttons „↑/↓“)
  - Optional: Download‑Umschalter (inline/attachment)
  - Komponenten‑Extraktion für Partials (`backend/web/components`)
