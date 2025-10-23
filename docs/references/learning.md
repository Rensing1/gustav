# Lernen (Learning) — Referenz

Ziel: Schülerzugriff auf freigegebene Inhalte, Abgaben (Text/Bild) mit Versuchszähler und sofortigem (Stub‑)Feedback. Dokumentiert API, Schema, RLS und Teststrategie.

## Endpunkte (API)
- `GET /api/learning/courses/{course_id}/sections?include=materials,tasks&limit&offset`
  - Liefert nur freigegebene Abschnitte für den eingeloggten Schüler (Mitgliedschaft erforderlich).
  - 200 `[{ section { id, title, position }, materials[], tasks[] }]`, 401/403/404.
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.

- `GET /api/learning/materials/{material_id}/download-url?disposition=inline|attachment`
  - Kurzlebige signierte URL für Datei‑Materialien, nur wenn Material in einem freigegebenen Abschnitt eines belegten Kurses liegt.
  - 200 `{ url, expires_at }`, 401/403/404.

- `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit&offset`
  - Eigene Abgaben zum Task in einem Kurskontext (Task kann in mehreren Kursen vorkommen).
  - 200 `[{ id, attempt_nr, kind, text_body?, mime_type?, size_bytes?, created_at, analysis_status, completed_at?, feedback_md? }]`, 401/403/404.
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.

- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`
  - Text‑Abgabe: `{ kind: 'text', text_body }`
  - Bild‑Abgabe: `{ kind: 'image', intent_id, sha256 }` (Intent vorher finalisiert)
  - Optionaler Header: `Idempotency-Key` (Dup‑Vermeidung bei Retries; gleiche Antwort, keine Doppelanlage)
  - Prüft: Mitgliedschaft, Release, `max_attempts`. 201 `Submission` (MVP synchron), optional 202 (Async‑Flag aktiv), 400/401/403/404.

- `POST /api/learning/submissions/upload-intents`
  - `{ filename, mime_type ('image/jpeg'|'image/png'), size_bytes ≤ 10MB }` → 201 `{ intent_id, url, fields, allowed_mime_types, max_size_bytes, expires_at }`.

- `POST /api/learning/submissions/finalize`
  - `{ intent_id, sha256 }` → 200 `{ intent_id, storage_key, sha256 }` (Hash‑Validierung erforderlich).
  - Orphan‑Cleanup: Intents besitzen TTL; abgelaufene/nie finalisierte Intents werden periodisch entsorgt.

- `GET /api/learning/submissions/{submission_id}/feedback`
  - 200 `{ analysis_status, analysis_json?, feedback_md? }` (MVP: synchron `completed`). 401/403/404.

Fehlercodes (Beispiele):
- 400: `invalid_input | invalid_uuid | invalid_file_type | file_too_large | max_attempts_exceeded`
- 403: `forbidden`
- 404: `not_found`

### Asynchron (optional, spätere Iteration)
- Motivation: Bei längerer Modelllaufzeit Rückmeldung nicht blockierend liefern.
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`
  - Rückgabe 202 Accepted mit `Location: /api/learning/submissions/{id}` und Body `Submission{ analysis_status='pending' }`.
  - Optional: `Retry-After: 2`, `Idempotency-Key` (Header) zur Doppelvermeidung bei Retries.
- `GET /api/learning/submissions/{submission_id}`
  - Polling: `pending|processing|completed|error`; bei `completed` enthält `feedback_md/analysis_json`.
- `GET /api/learning/submissions/{submission_id}/feedback`
  - Shortcut für Analysefelder, gleiches Status‑Verhalten.
- Optional: `GET /api/learning/submissions/{submission_id}/events` (SSE) für Live‑Updates.
- Rückwärtskompatibilität: MVP bleibt synchron (201 `completed`); Umschalten auf 202 erfordert nur Server‑Konfiguration.

## Schema & Migrationen (Supabase/PostgreSQL)
- Submissions: `supabase/migrations/20251024121001_learning_submissions.sql`
  - `public.learning_submissions` (siehe Plan‑Dokument für Felder/Constraints)
  - Indizes: `(course_id, task_id, student_sub)`, `created_at`
- RLS/Policies: `supabase/migrations/20251024121002_learning_rls_policies.sql`
  - SELECT nur eigene Datensätze; INSERT nur bei Sichtbarkeit (Mitgliedschaft + Release); UPDATE/DELETE im MVP nicht vorgesehen
- Helper/Guards: `supabase/migrations/20251024121003_learning_helpers.sql`
  - `check_task_visible_to_student(sub text, course_id uuid, task_id uuid) returns boolean` (SECURITY DEFINER, `set search_path = public, pg_temp`)
  - `next_attempt_nr(course_id uuid, task_id uuid, student_sub text) returns int` (SECURITY DEFINER, `set search_path = public, pg_temp`)
- Optionale View: `supabase/migrations/20251024121004_learning_released_items_view.sql`
  - `view_released_section_items_for_student(course_id, sub)` bündelt freigegebene Materials/Tasks

Asynchron‑Erweiterung:
- Jobs: `supabase/migrations/20251024121005_learning_jobs.sql`
  - `public.learning_analysis_jobs (id, submission_id, kind, status, attempts, ready_at, started_at, finished_at, last_error)`
- RLS/Policies für Jobs: `supabase/migrations/20251024121006_learning_jobs_rls.sql`
- Optional Trigger: `supabase/migrations/20251024121007_learning_job_triggers.sql`

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

## Sicherheit & Datenschutz
- Minimierte DTOs: Identität über `sub`, kein PII in API‑Antworten oder Presigned‑URLs.
- Presigned‑URLs: kurze TTL (2–5 Min.), `disposition=inline|attachment`, MIME‑Whitelist, Größenlimit 10 MB.
- Fehlersemantik: 404 bei nicht freigegebenen/fremden Ressourcen, um keine Existenzinformationen zu leaken.
 - Markdown‑Sanitizing: `body_md` (Materials) und `feedback_md` (KI‑Antwort) werden serverseitig sicher zu HTML gerendert (kein unsicheres Inline‑HTML; Sanitizer aktiv), um XSS zu verhindern.
 - HTTP‑Header (Learning‑API/Frontend): `Cache-Control: private, max-age=0`, `Referrer-Policy: no-referrer`. CSP im Frontend strikt: `img-src`/`frame-src` nur eigene Domains/Storage‑Domain; `object-src 'none'`.
 - Logging: Presigned‑URL‑Querystrings werden nicht geloggt.

## Architektur & Adapter
- Web‑Adapter: `backend/web/routes/learning.py`
- Repo (DB): `backend/learning/repo_db.py` (psycopg3)
- Use‑Cases: `backend/learning/usecases/*`
- Analyse‑Adapter: `backend/learning/analysis_adapter.py` (MVP: synchroner Stub; später DSPy/Ollama/vllm/llama.cpp/lemonade)
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
