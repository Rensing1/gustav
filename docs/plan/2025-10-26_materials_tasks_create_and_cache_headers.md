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
- `/units/{unit_id}` (bereits vorhanden: „Abschnitte verwalten“)
  - Jede Abschnittskarte erhält eine Schaltfläche „Material & Aufgaben“, die zur Detailseite führt: `/units/{unit_id}/sections/{section_id}`.

- `/units/{unit_id}/sections/{section_id}` (neu: Abschnitts‑Detailverwaltung)
  - Layout: Zweispaltig auf Desktop, einspaltig auf Mobil.
    - Linke Spalte: „Materialien“
      - Formular „Neues Material (Markdown)“ mit Feldern `title`, `body_md`; `hx-post` an UI‑Route, Ziel ist die Material‑Liste.
      - Sekundäre Aktion „Datei hochladen“: startet 2‑Phasen‑Flow (Upload‑Intent → Direkt‑Upload → Finalize). UI ruft nacheinander die API‑Endpunkte auf und aktualisiert die Liste nach erfolgreichem Finalize.
      - Liste der Materialien inkl. Drag‑Handle für Reorder.
    - Rechte Spalte: „Aufgaben“
      - Formular „Neue Aufgabe“ mit `instruction_md`, optional `criteria[]`, `hints_md`, `due_at`, `max_attempts`.
      - Liste der Aufgaben inkl. Drag‑Handle für Reorder.
  - Fehlermeldungen werden oberhalb des jeweiligen Formulars angezeigt (`role="alert"`).
  - CSRF: Hidden‑Field `csrf_token` analog zu `/courses`/`/units`.

UI‑Routen (nur HTML, rufen intern JSON‑API)
- GET `/units/{unit_id}/sections/{section_id}`
  - Holt via API: Unit, Section, Materials (GET `/api/…/materials`), Tasks (GET `/api/…/tasks`)
  - Rendert zwei Kartenbereiche mit Create‑Form und Listencontainern
  - Response‑Header: `Cache-Control: private, no-store`
- POST `/units/{unit_id}/sections/{section_id}/materials/create`
  - Validiert CSRF, ruft POST `/api/…/materials` und rendert den Material‑Listen‑Partial neu (HX‑Target: `#material-list-section-{section_id}`)
- POST `/units/{unit_id}/sections/{section_id}/materials/reorder`
  - Liest Sortierreihenfolge aus DOM (hx‑ext=sortable), ruft POST `/api/…/materials/reorder`, rendert Liste neu
- POST `/units/{unit_id}/sections/{section_id}/tasks/create`
  - Validiert CSRF, ruft POST `/api/…/tasks`, rendert Aufgaben‑Liste neu (HX‑Target: `#task-list-section-{section_id}`)
- POST `/units/{unit_id}/sections/{section_id}/tasks/reorder`
  - Analog Materialien
- Upload‑Flow (Datei‑Material):
  - POST `/units/{unit_id}/sections/{section_id}/materials/upload-intent` → ruft API `materials/upload-intents`, UI zeigt Upload‑URL/Headers (oder nutzt fetch) an
  - POST `/units/{unit_id}/sections/{section_id}/materials/finalize` → ruft API `materials/finalize`, danach Liste neu laden

Listen‑Partials (HTML‑IDs & Reorder)
- Materialien: Wrapper `<section id="material-list-section-{section_id}">` mit innerem `<div class="material-list" hx-ext="sortable" data-reorder-url="…/materials/reorder">` und Items `<div class="card material-card" id="material_{id}">`.
- Aufgaben: Wrapper `<section id="task-list-section-{section_id}">` mit `<div class="task-list" hx-ext="sortable" data-reorder-url="…/tasks/reorder">` und Items `<div class="card task-card" id="task_{id}">`.
- Drag‑Handle Symbol `☰` als Griff; Fallback‑Buttons „Nach oben/Nach unten“ für Tastaturbedienung.

Fehlertypen (UI‑Mapping)
- 400 → zeige validierte `detail` über dem Formular (z. B. `invalid_title`, `invalid_instruction_md`).
- 403 → Banner „Keine Berechtigung“; verlinke zurück zu `/units`.
- 404 → Banner „Abschnitt nicht gefunden“; verlinke zurück zu `/units`.

Detailseiten für einzelne Einträge (im Scope dieser Iteration)
- Routen:
  - GET `/units/{unit_id}/sections/{section_id}/materials/{material_id}`
  - GET `/units/{unit_id}/sections/{section_id}/tasks/{task_id}`
- Inhalt:
  - Material: Vollansicht (Markdown gerendert) bzw. Dateidownload‑Aktionen, Meta (MIME, Größe), Bearbeiten‑Button (PATCH via API), Entfernen.
  - Aufgabe: Volltext `instruction_md`, Kriterienliste, Fälligkeitsdatum, max. Versuche; Bearbeiten/Entfernen.
- Nutzen:
  - Klare Fokussicht pro Eintrag; Vorbereitung für Versionsverläufe/Audit und Kommentierung.

## Nächste Schritte (Umsetzung)

1) Abschnitts‑Detailseite (SSR) anlegen
- GET `/units/{unit_id}/sections/{section_id}` in `backend/web/main.py`
- Intern: `GET /api/teaching/units/{unit_id}`, `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials`, `GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks`
- HTML: Zweispaltiges Layout, je ein Create‑Formular und eine Liste mit Reorder (hx-ext=sortable)
- Header: `Cache-Control: private, no-store`

2) Materialien (Markdown) — Create + List + Reorder (UI)
- POST UI‑Route `/units/{unit_id}/sections/{section_id}/materials/create` → ruft API `POST …/materials`
- POST UI‑Route `/units/{unit_id}/sections/{section_id}/materials/reorder` → ruft API `POST …/materials/reorder`
- CSRF validieren, Fehler ins Formular mappen

3) Materialien (Datei‑Upload) — 2‑Phasen‑Flow (Intent → Upload → Finalize)
- UI‑Route `/materials/upload-intent` → ruft API `…/materials/upload-intents`, zeigt URL/Headers
- Client‑Upload (fetch oder `<form enctype>`), danach UI‑Route `/materials/finalize` → ruft API `…/materials/finalize`
- Nach Erfolg Liste neu laden; Fehlermeldungen (mime_not_allowed, checksum_mismatch) anzeigen

4) Aufgaben — Create + List + Reorder (UI)
- POST UI‑Route `/units/{unit_id}/sections/{section_id}/tasks/create` → ruft API `POST …/tasks`
- POST UI‑Route `/units/{unit_id}/sections/{section_id}/tasks/reorder` → ruft API `POST …/tasks/reorder`
- Validierungen (instruction_md, criteria, due_at, max_attempts) sauber mappen

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
  - Tests (pytest): `backend/tests/test_teaching_section_detail_ui.py`
    - Rendert Wrapper + Cache‑Header
    - Create‑Flows (Material Markdown, Task minimal)
    - Reorder‑Flows (Material/Task) inkl. CSRF‑Negativfall

- Offene Punkte (nächste Schritte):
  - Datei‑Upload (2‑Phasen) in der UI verdrahten:
    - `POST /units/{u}/sections/{s}/materials/upload-intent` (UI) ruft API‑Intent, zeigt URL/Headers
    - Upload clientseitig, danach `POST /…/materials/finalize` (UI) → API finalize, Liste aktualisieren
    - Fehlerabbildung (mime_not_allowed, checksum_mismatch, intent_expired) in UI‑Banner
  - Detailansichten pro Eintrag (Anzeige/Bearbeiten):
    - GET `/units/{u}/sections/{s}/materials/{m}` und `/tasks/{t}` (SSR)
  - UI‑Fehlermapping verbessern (Formfehlermeldungen, i18n‑Keys) und A11y‑Labels ergänzen
  - Evtl. kleine Komponenten für Listen‑Partials (`backend/web/components`) extrahieren
