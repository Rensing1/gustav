# Lernen (Learning) — Referenz

Ziel: Schülerzugriff auf freigegebene Inhalte und Abgaben (Text/Bild/PDF) mit Versuchszähler und KI-gestützter Auswertung. Dokumentiert API, Schema, RLS und Teststrategie für den Learning-Bounded-Context.

**Hinweis**: Details zur KI-Architektur, Adapter-Schnittstellen, Worker-Workflow und Monitoring stehen in `docs/references/learning_ai.md`.

Hinweis (Breaking, 2025‑10‑28): `LearningSectionCore` verlangt jetzt das Feld `unit_id`. Aktualisiere ggf. generierte Client‑Modelle.

## Endpunkte (API)
- `GET /api/learning/courses?limit&offset`
  - Liefert die Kurse, in denen der eingeloggte Schüler Mitglied ist (alphabetisch: `title asc`, sekundär `id asc`).
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.

- `GET /api/learning/courses/{course_id}/sections?include=materials,tasks&limit&offset`
  - Liefert nur freigegebene Abschnitte für den eingeloggten Schüler (Mitgliedschaft erforderlich).
- 200 `[{ section { id, title, position, unit_id }, materials[], tasks[] }]`, 401/403/404.
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.
  - Query `include`: CSV‑Liste im Stil `form`, `explode: false` (z. B. `include=materials,tasks`).

- `GET /api/learning/courses/{course_id}/units/{unit_id}/sections?include=materials,tasks&limit&offset`
  - Liefert nur freigegebene Abschnitte der angegebenen Lerneinheit im Kurs (Server‑Filter nach `unit_id`).
  - 200 Liste (ggf. leer); 400 bei Invalid‑UUID; 401/403 wie oben; 404 bei Kurs/Unit‑Mismatch.
  - Cache: `Cache-Control: private, no-store`.
  - Query `include`: CSV‑Liste im Stil `form`, `explode: false`.

- `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit&offset`
  - Liefert die eigenen Abgaben zu einer Aufgabe (`limit [1..100]`, default 20; `offset ≥ 0`).
  - Sortierung: `created_at desc`, sekundär `attempt_nr desc` (stabile Reihenfolge bei gleichen Timestamps).
  - 200 `[{ id, attempt_nr, kind, storage_key?, analysis_status, error_code?, analysis_json, feedback_md, created_at, completed_at, ... }]`.
    - `analysis_status ∈ {pending, extracted, completed, failed}`  
      - `pending`: Submission gespeichert, Analyse (OCR/Feedback) steht aus.  
      - `extracted`: Nur bei PDF‑Abgaben; PDF wurde erfolgreich in Seiten/Text zerlegt, Feedback steht noch aus.  
      - `completed`: Analyse inkl. Feedback abgeschlossen, `analysis_json`/`feedback_md` befüllt.  
      - `failed`: Verarbeitung abgebrochen; Details über `error_code`.  
    - `error_code` (optional) ist einer der normalisierten Fehlercodes  
      `vision_retrying | vision_failed | feedback_retrying | feedback_failed | input_corrupt | input_unsupported | input_too_large`.  
      `*_retrying` signalisiert in‑flight Retries, `*_failed` endgültige Abbrüche in Vision/Feedback, `input_*` Validierungs‑/Pre‑Processing‑Fehler vor dem eigentlichen KI‑Lauf.
  - 400/401/403/404.

- `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents`
  - Request: `{ kind: 'image' | 'file', mime_type, size_bytes }`
  - Response: `200 { storage_key, upload_url, headers, expires_at }`
    - `storage_key` Namespaces: `submissions/{course_id}/{task_id}/{student_sub}/{timestamp}-{uuid}.{ext}`
    - `mime_type` whitelist: `image/jpeg`, `image/png`, `application/pdf`
    - Gültigkeit der Presign-URL ≤ 10 Minuten
  - Fehler: 400 (`mime_not_allowed`, `size_exceeded`), 403 (CSRF/RLS), 404 (Task nicht sichtbar)

- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`
  - Alle Submission‑Typen (text/image/file) sind standardmäßig asynchron → Response `202` mit `analysis_status='pending'`.
  - Optionaler 201‑Fast‑Path für Text ist vertraglich dokumentiert, derzeit aber deaktiviert.
  - Aufrufe mit `Idempotency-Key` (≤ 64 Zeichen) sind idempotent.
  - Server prüft Mitgliedschaft, Release, `max_attempts`, CSRF (Same-Origin), Dateigrößen, Hash, Storage-Key-Regex.
  - Sobald der Worker OCR/Feedback abgeschlossen hat, wird die Submission auf `analysis_status='completed'` aktualisiert (oder `failed` bei Fehlern). Client kann via `GET` pollend den Status abfragen.

Fehlercodes (Beispiele):
- 400: `invalid_input | invalid_image_payload | invalid_file_payload | invalid_uuid | max_attempts_exceeded`
- 403: `forbidden`
- 404: `not_found`
- 409: `conflict` (bei mehrfacher Idempotency-Verwendung mit nicht übereinstimmendem Payload)

### Ausblick
- WebSocket/Push-Benachrichtigungen für `analysis_status` sind geplant. Bis dahin erfolgt Polling durch den Client.

## Schema & Migrationen (Supabase/PostgreSQL)
- Submissions: `supabase/migrations/20251023093409_learning_submissions.sql` + Folge-Migration (siehe Plan 2025‑11‑01)
  - Tabelle `public.learning_submissions` (immutable Entries, Attempt-Zähler, optionale Storage-Metadaten)
  - Seit 2025‑11: Telemetriespalten  
    - `vision_attempts int`, `vision_last_error text`, `vision_last_attempt_at timestamptz`  
    - `feedback_last_attempt_at timestamptz`, `feedback_last_error text`  
    - `analysis_status`‑Check auf `pending|extracted|completed|failed`
  - Indizes: `(course_id, task_id, student_sub)`, `created_at desc`, `student_sub/task_id/created_at desc`
  - JSON-Feld `analysis_json` folgt dem Schema `criteria.v1`:
    `{ schema: "criteria.v1", score: 0..5, criteria_results: [{ criterion, score: 0..10, explanation_md }] }`.
    `feedback_md` enthält das Markdown‑Feedback für Lernende.  
    Telemetriefelder (`vision_attempts`, `vision_last_error`, `feedback_last_attempt_at`, `feedback_last_error`) werden vom Worker gesetzt und sind für Schüler/Lehrkräfte lesbar, aber serverseitig sanitisiert (Strings gekürzt, Pfade/Secrets entfernt). Details zur Semantik siehe `docs/references/learning_ai.md` (Abschnitt „Telemetry Surfaces“).
- Queue-Tabelle: `public.learning_submission_jobs` mit Leasingfeldern (`lease_key`, `leased_until`), Status `queued|leased|failed` und Index auf `(status, visible_at)`.
- Helper-Funktionen: `supabase/migrations/20251023093417_learning_helpers.sql`
  - `hash_course_task_student`, `next_attempt_nr`, `check_task_visible_to_student`
  - `get_released_sections/materials/tasks_for_student`, `get_task_metadata_for_student`
    (liefert seit 2025-10-28 zusätzlich `criteria text[]` für Rubrik-Anzeigen)
- RLS-Policies: `supabase/migrations/20251023093421_learning_rls_policies.sql`
  - SELECT limitiert auf eigene `student_sub`; INSERT prüft Sichtbarkeit via `check_task_visible_to_student`
- Hardening-Fix: `supabase/migrations/20251023111657_learning_tasks_rls_fix.sql`
  - Stellt sicher, dass `get_released_tasks_for_student` nur freigegebene Sectionen liefert (`module_section_releases.visible = true`)
- Worker-Updates: erfolgen über `SECURITY DEFINER`-Funktion `learning_submission_ocr_process_job` (nicht Bestandteil des ursprünglichen MVP, siehe AI-Referenz).

Bezüge zu Unterrichten (bestehende Tabellen):
- `public.units`, `public.unit_sections`, `public.unit_materials`, `public.unit_tasks`
- `public.course_modules` (Unit‑→Kurs), `public.module_section_releases` (Freigaben)
- `public.courses`, `public.course_memberships`

## RLS & DSN
- App‑Role: `gustav_limited`; jede DB‑Operation setzt `SET LOCAL app.current_sub = '<sub>'`.
- RLS:
  - Submissions SELECT: nur `student_sub = app.current_sub`.
  - Submissions INSERT: nur wenn `check_task_visible_to_student` true und `max_attempts` nicht überschritten.
  - Keine UPDATE/DELETE im MVP (Abgaben sind unveränderlich).
- Rollbacks löschen Transaktions-GUCs. Nach `conn.rollback()` muss der Repo-Code `set_config('app.current_sub', student_sub, true)` neu setzen, bevor weitere Statements laufen (siehe `DBLearningRepo.create_submission`).
- DSN‑Auflösung (Learning‑Repo): `LEARNING_DATABASE_URL` > `LEARNING_DB_URL` > `RLS_TEST_DSN` > `DATABASE_URL` > Fallback (dev/test): `postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres`. In PROD ist ein expliziter DSN erforderlich.
- Helper laufen als SECURITY INVOKER mit gehärtetem `search_path`; zusätzliche Grants für
  `supabase_admin` sind nicht erforderlich, solange Migrationen mit Standard-Supabase-Rollen laufen.
- Zusätzliche SELECT-Policies erlauben Schülern (über `gustav_limited`) Lesezugriff nur auf freigegebene
  Kursinhalte: Units, Course Modules, Unit Sections, Module Section Releases (sichtbare), Unit Materials
  und Unit Tasks. Die Policies prüfen Mitgliedschaft (`course_memberships`) und Freigaben (`visible`).
- Spezifische Prüffunktionen für Schülerzugriff:
  - `student_is_course_member(p_student_sub text, p_course_id uuid)`
  - `student_can_access_unit(p_student_sub text, p_unit_id uuid)`
  - `student_can_access_course_module(p_student_sub text, p_course_module_id uuid)`
  - `student_can_access_section(p_student_sub text, p_section_id uuid)`
  Diese Funktionen laufen als SECURITY INVOKER und besitzen nur EXECUTE für `gustav_limited`.

## Sicherheit & Datenschutz
- Minimierte DTOs: Identität über `sub`, kein PII in API‑Antworten.
- Fehlersemantik: 404 bei nicht freigegebenen/fremden Ressourcen, um keine Existenzinformationen zu leaken.
- Materials & Tasks: Markdown wird serverseitig sanitisiert, `Cache-Control: private, no-store`.
- Fehlerantworten: 400/401/403/404 der Learning‑Endpoints senden ebenfalls `Cache-Control: private, no-store`.
- Submissions: Storage-Metadaten werden bei Bildabgaben geprüft; `storage_key` wird in API‑Antworten zurückgegeben (nur für `kind=image`). Hash-Format (`sha256`) wird geprüft, bevor Daten persistiert werden.
- Bild‑Uploads: MIME‑Typ‑Whitelist (`image/jpeg`, `image/png`) und strenges `storage_key`‑Pattern (pfadähnlich, keine Traversal‑Segmente).
- CSRF: Same‑Origin‑Prüfung nutzt `Origin`, fällt bei fehlendem `Origin` auf `Referer` zurück (nur Origin‑Teil, Pfad ignoriert). Nicht‑Browser‑Clients bleiben unverändert (keine Header).
  Reverse‑Proxy‑Header (`X‑Forwarded‑Proto`/`X‑Forwarded‑Host`/`X‑Forwarded‑Port`) werden nur berücksichtigt, wenn `GUSTAV_TRUST_PROXY=true` gesetzt ist (z. B. hinter Caddy/Nginx). Ohne diese Variable werden Forwarded‑Header ignoriert, um Header‑Spoofing zu vermeiden.
- DB‑Funktionen (SECURITY DEFINER): Alle Helfer (`get_released_*`, `check_task_visible_to_student`, `next_attempt_nr`) verwenden gehärtete `search_path`‑Einstellungen (`pg_catalog, public`) und vollqualifizierte Tabellennamen, um Hijacking über fremde Schemas zu verhindern.
- Logging: Keine Payload-Inhalte für Submissions in Standard-Logs.

### `LearningSubmission` (API)
- `analysis_status`: `pending | extracted | completed | failed`  
  - `pending`: Submission ist gespeichert, Worker hat Vision/Feedback noch nicht ausgeführt.  
  - `extracted`: Nur PDF‑Pfad – PDF wurde in Seiten/Text zerlegt, Feedback steht noch aus.  
  - `completed`: Analyse inkl. Feedback ist abgeschlossen, `analysis_json`/`feedback_md` sind gesetzt.  
  - `failed`: Verarbeitung wurde abgebrochen; `error_code` beschreibt die Ursache.
- `error_code` (optional):  
  `vision_retrying | vision_failed | feedback_retrying | feedback_failed | input_corrupt | input_unsupported | input_too_large`.  
  Die `vision_*`‑Codes beziehen sich auf den OCR‑Adapter, `feedback_*` auf die Feedback‑KI; `input_*` signalisiert Probleme mit der Eingabe (z. B. beschädigte oder zu große Dateien).  
- `analysis_json`: Struktur nach `criteria.v1` oder `criteria.v2` (siehe oben bzw. AI‑Referenz). In der Async‑Pipeline ist dieses Feld während `pending` und `extracted` `null` und wird erst nach Abschluss gesetzt.  
- `feedback_md`: Markdown für formatives Feedback (Stub in Dev; KI‑Ausgabe produktiv).  
- Telemetrie (`SubmissionTelemetry`):  
  - `vision_attempts` (int, ≥0): Anzahl Vision/OCR‑Versuche.  
  - `vision_last_error` (text, nullable): letzte, bereits bereinigte Fehlermeldung des Vision‑Adapters.  
  - `feedback_last_attempt_at` (timestamptz, nullable): Zeitpunkt des letzten Feedback‑Versuchs.  
  - `feedback_last_error` (text, nullable): letzte, bereinigte Fehlermeldung des Feedback‑Adapters.  
  Alle Texte sind serverseitig sanitisiert (Länge ≤ 256, keine Pfade/Secrets). Für weitere Details siehe `docs/references/learning_ai.md` (Telemetry‑Abschnitt).  
- `created_at`: RFC3339‑Zeitstempel in UTC mit explizitem `+00:00`‑Offset (z. B. `2025-10-23T09:45:00+00:00`).

## Architektur & Adapter
- Web‑Adapter: `backend/web/routes/learning.py`
- Repo (DB): `backend/learning/repo_db.py` (psycopg3)
- Use‑Cases: `backend/learning/usecases/*`
- Analyse‑Stub: aktuell direkt im Repo (`_build_analysis_payload` in `backend/learning/repo_db.py`); spätere Iteration ersetzt dies durch echte KI-Adapter (DSPy/Ollama/vllm/llama.cpp/lemonade).
- Storage‑Adapter: Re‑Use `teaching.storage_supabase.SupabaseStorageAdapter` mit separatem Prefix (z. B. `submissions/`).
 - Asynchron: Einfacher Worker‑Prozess/Container mit Claim‑Loop (`FOR UPDATE SKIP LOCKED`), getrennte OCR‑ und Analyse‑Jobs möglich.

## Tests
- API‑Tests: `backend/tests/test_learning_*.py` (Contract, Fehlerpfade, Attempt‑Limit, Upload‑Flow)
- DB‑Optionals: RLS‑Smoke‑Tests nur mit Limited‑DSN, `set_config('app.current_sub', ...)` je Session

## Anwenden lokal
- `supabase migration up`
- `.venv/bin/pytest -q`

## DSGVO / Audit
- Timestamps `created_at` und `completed_at` je Abgabe.
- Keine Speicherung von Klarnamen in Learning‑Tabellen; Auflösung von Anzeigenamen erfolgt ausschließlich im UI über Directory‑Adapter.
## Schüler‑UI: Lerneinheit mit Abschnitten
- Route: `/learning/courses/{course_id}/units/{unit_id}` (SSR)
- Darstellung:
  - Abschnittstitel werden ausgeblendet; Gruppen sind durch genau eine horizontale Linie `<hr>` getrennt.
  - Innerhalb eines Abschnitts werden Materialien (Markdown/File) und Aufgaben in der kursüblichen Reihenfolge dargestellt.
  - Bei keiner Freigabe zeigt die Seite einen neutralen Hinweis.
- Datenquelle: der obige Unit‑Sections‑Endpoint mit `include=materials,tasks`.
- Sicherheit: Seite setzt `Cache-Control: private, no-store`.

## Schüler‑UI: Kursansicht (Units‑Liste)
- Route: `/learning/courses/{course_id}` (SSR)
- Darstellung:
  - Listet alle Lerneinheiten des Kurses mit Position als Badge.
  - Jeder Eintrag verlinkt auf `/learning/courses/{course_id}/units/{unit_id}`.
  - Kein Bearbeiten/Sortieren (read‑only für Schüler).
- Sicherheit: Seite setzt `Cache-Control: private, no-store`.
