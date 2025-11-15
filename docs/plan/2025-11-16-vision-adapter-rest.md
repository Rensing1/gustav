# 2025-11-16 – Vision Adapter Must-Fix Rest

Status: in Arbeit

## Hintergrund
- Bezug: Must-Fix 1 „Vision Adapter zu komplex“ aus `docs/plan/2025-11-14-PR-fix3.md`.
- Bisher erledigt: Host/Port-Validierung + Remote-Fetch-Tests (`2025-11-15-local-vision-hardening.md`).
- Offen: Adapter in kleinere Helfer zerlegen, PDF-Pipeline (Cache vs. Remote Render) testen, Logging vereinheitlichen, damit der Code KISS bleibt und Audits erleichtert werden.

## User Story
> Als Lernplattform-Operator:in möchte ich, dass der Local-Vision-Adapter klar strukturierte Helfer für Bytes-Beschaffung, PDF-Stitching und Modellaufrufe benutzt, damit sicherheitskritische Pfade leicht auditierbar und wartbar bleiben.

## BDD-Szenarien
1. **Given** ein vorhandenes `derived/<submission_id>/stitched.png`, **When** der Adapter PDF-Bilder benötigt, **Then** er nutzt den Cache ohne Remote-Fetch oder Rendering (`action=cached_stitched` geloggt).
2. **Given** kein Cache, aber `internal_metadata.page_keys` mit gültigen PNGs, **When** PDF-Bilder angefordert werden, **Then** Helper liest Seiten, stitched sie, persistiert `stitched.png` und loggt `action=stitch_from_pages`.
3. **Given** weder Cache noch Seitenbilder vorhanden, aber Supabase-Service-Role nutzbar, **When** Adapter versucht Rendern, **Then** er ruft Download-Helper → Prozess → Persist, loggt `action=render_remote` und reicht PNG an das Modell.
4. **Given** Remote-Fetch scheitert (HTTP 302), **When** Adapter versucht PDF-Bilder zu laden, **Then** Download-Helper liefert `redirect`, Adapter wirft `VisionTransientError("remote_fetch_failed")` und loggt `reason=redirect`.
5. **Given** Logging-Helper erhält Submission-Daten, **When** Fehlermeldungen entstehen, **Then** Logeinträge enthalten `submission_id`, `action`, `reason` aber niemals Bucket-/Studenten-IDs.

## API / Vertrag
- Keine API-Änderungen (internes Worker-Modul). `api/openapi.yml` bleibt unverändert.

## Datenmodell / Migration
- Keine Schemaänderungen nötig → keine Supabase-Migration.

## Teststrategie (TDD)
1. Neuer Test `backend/tests/learning_adapters/test_local_vision_pdf_cached_stitched.py`:
   - Arrange: Filesystem mit fertigem `stitched.png`.
   - Assert: Adapter ruft Modell mit genau diesem Bild, Logging enthält `cached_stitched`, kein HTTP-Download.
2. Neuer Test `test_local_vision_pdf_page_keys_stitch.py`:
   - Provide `internal_metadata.page_keys` → Helper liest Dateien, persistiert `stitched.png`, ruft Modell mit Ergebnis.
3. Neuer Test `test_local_vision_pdf_logging_helpers.py`:
   - Simuliere Remote-Fetch-Redirect; verifiziere `VisionTransientError("remote_fetch_failed")` + Log-Helper-Output ohne PII.
4. Refactor Tests:
   - Gemeinsame Fixtures/Helpers (z. B. `FakeHttpxClient`, `FakeOllamaClient`) aus bestehenden Tests extrahieren, damit neue Szenarien leichter abgedeckt werden.

## Aufgaben
1. Gemeinsame Test-Hilfsfunktionen für Vision-Adapter hinzufügen (optional neues Testmodul `conftest` oder Helper-Datei).
2. Neue pytest-Dateien (siehe Teststrategie) schreiben – erwartungsgemäß rot.
3. Adapter refaktorieren:
   - `_fetch_storage_bytes`, `_ensure_pdf_image_bytes`, `_call_model` etc. mit Docstrings + Inline-Kommentaren.
   - Logging-Helper (`_log_event(submission_id, action, **fields)`) für konsistente, PII-freie Nachrichten.
4. Tests grün machen, minimaler Code für Rot-Grün.
5. Docs aktualisieren:
   - `docs/plan/2025-11-14-PR-fix3.md` Fortschrittseintrag.
   - `docs/CHANGELOG.md` + `docs/references/learning_ai.md` kurze Notizen zur Refaktorierung.

## Risiken
- Über-Refaktorierung → Tests schwer wartbar. Gegenmaßnahme: Nur Helfer extrahieren, die direkt von Tests abgedeckt werden.
- Dateisystempfade beinhalten PII → Logging-Helper muss konsequent redigieren.
- PDF-Verarbeitung kann teuer sein → sicherstellen, dass Caching-Path bevorzugt wird (Tests validieren).

## Fortschritt
- 2025-11-16: Erste Testwelle (`test_local_vision_pdf_cached_paths.py`) beschreibt Cache-, Page-Key- und Redirect-Szenarien (rot → grün).
- 2025-11-16: `_log_storage_event` eingeführt; `_ensure_pdf_stitched_png` priorisiert Cache/Page-Keys, loggt strukturierte Aktionen und behandelt Supabase-Redirects mit `VisionTransientError("remote_fetch_failed")`.
- 2025-11-16: Erweiterte Remote-Tests (`test_local_vision_remote_fetch.py`, `test_local_vision_missing_bytes_transient.py`) erzwingen Telemetrie (`action=fetch_remote_image`) und Fehler-Mapping (`VisionTransientError("remote_fetch_failed")`) auch für JPEG/PNG.
- 2025-11-16: Helper `_resolve_submission_image_bytes` + `_load_local_storage_bytes` kapseln nun Pfad-/Size-/Hash-Prüfungen für JPEG/PNG (inkl. Tests `test_resolve_image_bytes_prefers_local...`). Der Adapter ruft die Helfer anstatt Inline-Logik auf, `test_local_vision_streaming.py::test_stream_size_mismatch_is_permanent` bleibt damit grün.
- 2025-11-16: `_call_model` bündelt den Ollama-Aufruf (Timeout/Error-Mapping, Markdown-Unwrap, images-Handling). Neue Tests `backend/tests/learning_adapters/test_local_vision_model_helper.py::*` beschreiben diese Erwartungen (Red → Green).
