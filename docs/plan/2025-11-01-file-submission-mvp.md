# Plan: Datei-/PDF-Abgaben im Lernen-Modul (MVP)

Datum: 2025-11-01
Autor: Felix & Assistent

## User Story
Als Schüler möchte ich unter jeder Aufgabe meine Lösung entweder als Text eingeben oder alternativ eine Datei (PDF bzw. Bild) hochladen können, damit ich flexibel Lösungen einreichen kann; in der Historie soll später der extrahierte Text angezeigt werden.

## Scope (MVP)
- Abgabearten: text, image (jpeg/png, vorhanden), file (PDF neu)
- Größenlimit: max. 10 MiB für image/file
- Historie: zeigt Analyse-Stub (Textplatzhalter/OCR-Platzhalter), kein echtes OCR
- UI: Textfeld + Toggle (Text/Bild/Dokument) unter Aufgabenkarte, Historie unterhalb

Nicht-Ziele (MVP):
- Echte OCR oder PDF-Text-Extraktion (nur Platzhalter)
- Word/ODT-Unterstützung (nur application/pdf)

## BDD-Szenarien (Given-When-Then)
1) Happy Path Text: enrolled student, section released → 201, attempt_nr=1, analysis_status=completed, Rubrik-Scores gem. Kriterien
2) Happy Path Bild: image/jpeg|png, ≤10 MiB → 201 mit Platzhaltertext und Feedback
3) Happy Path PDF: application/pdf, ≤10 MiB → 201 mit Platzhaltertext und Feedback
4) Historie: mehrere Versuche → GET liefert nur eigene Versuche, neueste zuerst
5) Idempotenz: gleicher Idempotency-Key → gleicher Versuch zurück (kein neuer)
6) Limitierung: max_attempts erreicht → 400 detail=max_attempts_exceeded
7) Validierung Text: leer/zu lang (>10k) → 400 invalid_input
8) Validierung Bild: MIME nicht erlaubt/illegaler storage_key/sha256/Größe>10MiB → 400 invalid_image_payload
9) Validierung Datei: MIME≠application/pdf/illegaler storage_key/sha256/Größe>10MiB → 400 invalid_file_payload
10) Auth: nicht eingeloggt → 401; kein Kursmitglied → 403
11) CSRF: Origin/Referer nicht same-origin → 403 csrf_violation
12) IDs: nicht-UUID → 400 invalid_uuid

## API Contract-First (OpenAPI Ausschnitt)
- Schema LearningSubmission.kind: enum [text, image, file]
- POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions
  - oneOf: text | image | file
  - image: mime ['image/jpeg','image/png'], size_bytes 1..10485760
  - file: mime ['application/pdf'], size_bytes 1..10485760

## Datenbank-Migration (Entwurf)
- learning_submissions.kind CHECK erweitern: ('text','image','file')
- Größen-Constraint: size_bytes null oder 1..10485760 (defense-in-depth)
- Keine weitere Schemaänderung nötig (Spalten existieren)

## Testplan (TDD)
Red:
- Ergänze Pytest-Tests für PDF-Happy-Path, MIME-Whitelist (file), Größenlimit (file)
- Erwartet 201 (happy) bzw. 400 invalid_file_payload (Fehlerfälle)

Green:
- Adapter-Validierung (Learning-Route): 'file' akzeptieren, MIME/Größe prüfen
- Repo: Analyse-Stub für 'file' ("PDF text placeholder for {filename}")
- Behalte Idempotenz, RLS, CSRF-Checks unverändert

Refactor:
- Gemeinsame Validierungshilfen (dry) und klare Benennung
- Konfigurierbare Limits (Konstante zentral)

## UI-Entwurf (MVP)
- TaskCard: Formular mit Umschalter (Text/Bild/Dokument)
- Text: textarea; Bild/PDF: Felder für storage_key, mime_type (fix), size_bytes, sha256
- Historie: Accordion mit Text der Analyse (Platzhalter)

## Risiken & Sicherheit
- RLS: nur eigene Abgaben sichtbar
- CSRF: Same-Origin für POST
- Upload-Pfade: strikte storage_key-Regel (keine Traversal)
- DSGVO: private, no-store Cache-Header

## Rollout
1) OpenAPI aktualisieren — erledigt
2) Red-Tests ergänzen — erledigt
3) Implementierung minimal, Green — erledigt
4) Migration ausführen — erledigt (supabase migration up)
5) UI anpassen — offen

### Laufende Notizen
- 2025-11-01 09:20: Datei-Varianten (file/PDF) in API & Validierung ergänzt; Analyse-Stub liefert „PDF text placeholder …“.
- 2025-11-01 09:22: Test schlug zunächst fehl (CheckViolation auf kind). Ursache: DB-Constraint erlaubte 'file' noch nicht.
- 2025-11-01 09:24: Migration angewendet (CHECK aktualisiert auf ('text','image','file') + Größenlimit). Erwartung: Tests nun grün.
- 2025-11-01 10:10: Phase 2 Red-Tests angelegt: Upload‑Intents (Vertrag/Verhalten) und SSR‑UI (Render/Submit/History). Vertrag aktualisiert (OpenAPI Pfad + Schemas).
- 2025-11-01 11:05: Lehr‑API Kompatibilitätsalias: `POST /api/teaching/courses/{id}/members` akzeptiert zusätzlich `{"sub": "..."}` neben `{"student_sub": "..."}`, um bestehende Tests/Clients nicht zu brechen. Langfristig nur `student_sub` dokumentieren.
- 2025-11-01 12:10: UI‑Historie Lazy‑Load: TaskCard rendert nun einen HTMX‑Platzhalter (`<section class="task-panel__history" hx-get=".../history" hx-trigger="load" hx-target="this" hx-swap="outerHTML">`). Bei PRG (show_history_for) werden die Einträge serverseitig eingeblendet.

---

# Phase 2: UI für Schüler-Abgaben (Form, Toggle, Upload)

Ziel: Unter jeder Aufgabe ein Abgabeformular (Text/Bild/PDF) und eine Historie anzeigen. Uploads (Bild/PDF) laufen über Pre‑Signed Upload Intents. Keine echten OCR/Extraktionen, nur Platzhalter.

## Neue User Stories
- Als Schüler möchte ich direkt unter einer Aufgabe eine Textantwort eingeben und absenden können, damit ich sofort Feedback erhalte.
- Als Schüler möchte ich alternativ ein Bild (JPEG/PNG) oder ein PDF hochladen und als Abgabe einreichen können, damit ich auch handschriftliche oder dokumentenbasierte Lösungen abgeben kann.
- Als Schüler möchte ich meine Abgabehistorie unter der Aufgabe sehen, um meine Fortschritte und das Feedback nachzuvollziehen.

## BDD-Szenarien (UI)
1) Rendern: Given freigeschaltete Aufgabe, When ich die Einheit öffne, Then sehe ich eine Aufgabenkarte mit Umschalter (Text/Bild/PDF) und einem aktiven Formular (standard: Text).
2) Abgabe Text Happy Path: Given Umschalter "Text" aktiv, When ich absende, Then PRG → Banner sichtbar und Historie zeigt neuesten Eintrag geöffnet.
3) Abgabe Bild Happy Path: Given Kursmitglied und freigeschaltete Aufgabe, When ich eine Bild‑Abgabe (storage_key, mime=image/png, size_bytes≤10MiB, sha256) via UI absende, Then PRG → Banner und Historie mit neuestem Eintrag geöffnet.
4) Abgabe PDF Happy Path: Given Kursmitglied und freigeschaltete Aufgabe, When ich eine PDF‑Abgabe (storage_key, mime=application/pdf, size_bytes≤10MiB, sha256) via UI absende, Then PRG → Banner und Historie mit neuestem Eintrag geöffnet.
5) Fehlerfall Upload‑Felder: Given unvollständige Felder (z.B. sha256 fehlt), When ich absende, Then API 400 → UI zeigt Fehlhinweis (Phase C – später).
2) Abgabe Text Happy Path: Given Umschalter auf Text, When ich Text sende, Then sehe ich eine Erfolgsmeldung und ein neuer Eintrag erscheint oben in der Historie.
3) Abgabe Bild Happy Path: Given Umschalter auf Bild, When ich eine PNG (≤10 MiB) hochlade und abschicke, Then wird ein Upload‑Intent erzeugt, die Datei hochgeladen, und anschließend wird eine Submission erstellt; Historie zeigt „OCR placeholder …“.
4) Abgabe PDF Happy Path: Given Umschalter auf Dokument, When ich ein PDF (≤10 MiB) hochlade und abschicke, Then wird ein Upload‑Intent erzeugt, die Datei hochgeladen, und anschließend wird eine Submission erstellt; Historie zeigt „PDF text placeholder …“.
5) Fehlerfälle Upload: Given GIF/zu groß/keine PDF, When ich hochlade, Then erhalte ich eine Validierungsmeldung (clientseitig und vom Server) und keine Submission wird erzeugt.
6) Versuchsgrenze: Given max_attempts erreicht, When ich erneut absende, Then sehe ich eine Fehlermeldung und es erscheint kein neuer Historieneintrag.
7) Idempotenz: Given instabile Verbindung, When ich erneut auf „Abgeben“ klicke, Then wird derselbe Versuch per Idempotency‑Key dedupliziert.
8) Historie Lazy‑Load: Given Aufgabenkarte, When ich „Historie anzeigen“ öffne, Then werden die letzten Abgaben on‑demand geladen (Pagination vorbereitet), um N+1 zu minimieren.

## API Contract-First (Erweiterungen für Upload)
Neue Endpunkte (Learning, Student):
- POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents
  - Request: { kind: 'image'|'file', filename: string, mime_type: string, size_bytes: integer }
  - Response: { intent_id: uuid, storage_key: string, url: uri, headers: object, accepted_mime_types: [string], max_size_bytes: int, expires_at: date-time }
  - Security: Cookie (student), Same‑Origin, Membership Guard, MIME‑Whitelist (image/jpeg,image/png bzw. application/pdf), Size ≤10 MiB
  - Zweck: Pre‑Signed Upload, danach POST /submissions mit {kind, storage_key, mime_type, size_bytes, sha256}

OpenAPI: Neuen Schematyp „StudentUploadIntentRequest/Response“ analog zu Material‑Intents ergänzen; Pfad unter „Learning“ aufnehmen.

## Datenbank/Migrationen
- Keine neuen Tabellen nötig für Upload‑Intents (stateless). Optional: Storage‑Bucket „submissions“ in lokaler Dev‑Konfiguration anlegen.
- Supabase (dev): config.toml → [storage.buckets.submissions] mit objects_path=./storage/submissions

## Tests (Red zuerst)
- API‑Vertrag: test_openapi_learning_upload_intents_contract — Pfad, Schemas, Security, Header.
- API‑Verhalten: test_learning_upload_intents_behavior — akzeptierte MIME/Größe, 403 für Nicht‑Mitglieder, 400 für GIF/zu groß, 503 wenn Storage nicht konfiguriert (NullAdapter).
- UI (SSR):
  - test_learning_ui_renders_task_form_with_toggle — Seite enthält Umschalter (Text/Bild/PDF) und Formularelemente (ohne Bild‑Vorschau/Thumbnail).
  - test_learning_ui_submit_text_updates_history — POST Text über UI‑Route → 303 PRG → Erfolgshinweis angezeigt → neuer Eintrag sichtbar und als neuester standardmäßig geöffnet.
  - test_learning_ui_history_lazy_load — Aufruf einer UI‑GET‑Route liefert HTML‑Fragment mit Historie (HTMX target), neuester Eintrag geöffnet.

## Implementierung (Green minimal)
1) OpenAPI: upload‑intents spezifizieren.
2) Learning‑Router: Implementiere POST /upload-intents mit Storage‑Adapter (Reuse teaching.storage Adapter; MIME/Size prüfen; Same‑Origin; Membership prüfen).
3) SSR (backend/web/main.py):
   - Erweiterung von learning_unit_sections: Render TaskCard mit form_html (Text‑Form) und History‑Container (leer). Toggle (Radio) schaltet sichtbar/unsichtbar Felder.
   - UI‑Route POST /learning/courses/{course_id}/tasks/{task_id}/submit (Form POST) → call API submissions; generiere Idempotency‑Key hidden; PRG zurück zur Einheit; einfacher Erfolgshinweis (Banner) auf Zielseite.
   - UI‑Route GET /learning/courses/{course_id}/tasks/{task_id}/history (HTMX) → rendert HTML der letzten n Submissions, neuester Eintrag geöffnet (details open).
   - Optional Phase B: Client‑seitiger Upload (JS): Hole Upload‑Intent, PUT zu url, berechne sha256 via WebCrypto, sende Submission JSON. Keine Bild‑Vorschau anzeigen (bewusst weggelassen).

## Refactor & Architektur
- Gemeinsame Storage‑Adapter‑Schnittstelle für Teaching & Learning (kein Duplikat).
- Helper für Binär‑Validierung (mime/size/sha/storage_key) wiederverwenden.
- Vermeide N+1: Historie per Lazy‑Load (HTMX), nicht beim initialen Rendern.

## Sicherheit
- CSRF: Same‑Origin für alle POSTs; SSR‑Formen optional mit Synchronizer Token (UI‑Routen) zusätzlich absichern.
- RLS: API hält Ownership/Membership; UI ruft nur interne API unter übernommener Session auf.
- Upload: Nur erlaubte MIME‑Typen; Max 10 MiB; strenger storage_key‑Regex.

## Aufgabenliste (TODO)
- [x] OpenAPI: Student Upload‑Intents spezifizieren
- [x] Tests: Vertrag + Verhalten für Upload‑Intents (Red)
- [x] Tests: UI Render/Submit/History (Red)
- [x] Learning‑Router: Upload‑Intents (Green minimal, Stub‑URL für Dev)
- [x] UI‑Routen: submit/history + SSR‑Render (Green minimal, Banner + neuester Eintrag offen)
- [ ] Optional: JS Upload Phase B (Green)
- [ ] Docs: Komponentendoku TaskCard‑Form und Sicherheitsnotizen

### UI/UX‑Entscheidungen (Stand: 2025‑11‑01)
- Keine Bild‑Vorschau/Thumbnails im Formular (Dateiname/Typ/Größe genügen).
- Einfacher Erfolgshinweis (Banner) nach Abgabe; keine Snackbar.
- Historie: neuester Eintrag standardmäßig geöffnet, ältere Einträge eingeklappt.


## Checklist
- [ ] OpenAPI angepasst
- [ ] Red-Tests (file) grün gemacht
- [ ] Größe ≤10 MiB erzwungen
- [ ] Doku/Kommentare hinzugefügt
- [ ] UI-Form und Historie ergänzt
