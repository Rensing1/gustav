# Plan: Lernen – MVP

Ziel: Minimal funktionsfähiger Lernen‑Kontext für Schüler, um freigegebene Inhalte zu sehen, Aufgaben zu bearbeiten und unmittelbares (Stub‑)Feedback zu erhalten. Umsetzung gemäß Clean Architecture, KISS, Security‑first, FOSS und Glossary.

## Scope (MVP)
- Sichtbarkeit: Schüler sehen nur Abschnitte, die im jeweiligen Kurs freigegeben sind (Release aus Unterrichten).
- Materialien lesen: Markdown und Dateien; Dateien wahlweise inline (`disposition=inline`) oder als Download.
- Aufgaben: Schüler können Text‑ oder Bild‑Abgaben (Submissions) erstellen; jede Abgabe ist unveränderlich, inkl. Zeitstempel und Versuchszähler.
- Feedback: MVP verwendet einen synchronen Analyse‑Stub (Deterministik, sofortiges `feedback_md`). Später binden wir echte Modelle über Adapter an (DSPy/Ollama/vllm/llama.cpp/lemonade).
- Aufgabenhistorie: Pro Aufgabe und Kurs wird eine geordnete Liste aller Abgaben angezeigt.

Nicht im MVP:
- Live‑Push/WebSocket, umfassendes Learning‑Dashboard, SM‑2/Spaced Repetition, komplexe Rubrics/Mehrsprachigkeit.

Annahmen & Schnittstellen:
- Unterrichten liefert: Kursmodule, Units/Sections, Materials, Tasks, Abschnitts‑Releases.
- RLS: DSN `gustav_limited`, `SET LOCAL app.current_sub` pro Request; Policies schützen Mitgliedschaft und Releases.
- Storage: Wiederverwendung des Supabase‑Storage‑Adapters; Upload‑Intents + Finalize auch für Bild‑Abgaben; MIME‑Whitelist `image/jpeg|image/png`, max. 10 MB.

MVP‑KI (festgelegt)
- Synchroner Stub: Im MVP erzeugen wir direkt im Create‑Submission‑Call deterministisches Feedback (keine Queue/Worker, kein 202 + Polling). Dadurch ist die Lernstrecke sofort erlebbar und zuverlässig testbar.
- Zukunft: Die Schnittstelle bleibt stabil, wir können später auf asynchron umstellen (Submission = `pending`, UI zeigt "Feedback wird erstellt…", später Abruf).
- Zwei Modell‑Adapter (vorbereitet):
  1) OCR/Handschrift‑Adapter für Bild‑Abgaben (macht aus Fotos/Scans Text).
  2) Analyse/Feedback‑Adapter, der den Text (getippt oder aus OCR) bewertet und Feedback erzeugt.
  Pipeline: Text‑Abgabe → Analyse; Bild‑Abgabe → OCR → Analyse. Die konkreten Inference‑Backends sind austauschbar.

## User Stories
1) Als Schüler sehe ich die für meinen Kurs freigegebenen Abschnitte inklusive Materialien und Aufgaben, damit ich weiß, was zu bearbeiten ist.
2) Als Schüler möchte ich Lösungen zu Aufgaben als Text oder Bild abgeben und sofort eine Rückmeldung erhalten, damit ich mein Lernen steuern kann.
3) Als Schüler möchte ich meine bisherigen Abgaben pro Aufgabe sehen, inklusive Status und Feedback, um meinen Fortschritt nachvollziehen zu können.

## BDD‑Szenarien (Given‑When‑Then)

1) Freigegebene Abschnitte sehen (Happy Path)
- Given: Schüler ist Mitglied des Kurses; Abschnitt A ist freigegeben.
- When: Schüler ruft `GET /api/learning/courses/{course_id}/sections?include=materials,tasks&limit=50&offset=0` auf.
- Then: Antwort enthält Abschnitt A mit Materials/Tasks; 200 OK.

2) Nicht freigegebenen Abschnitt nicht sehen (Sicherheit)
- Given: Schüler ist Mitglied des Kurses; Abschnitt B ist nicht freigegeben.
- When: Schüler ruft die Sections‑Liste auf.
- Then: Abschnitt B fehlt; keine Informationen werden geleakt.

3) Dateien inline einbinden (Happy Path)
- Given: Datei‑Material M (PDF/Bild) gehört zu freigegebenem Abschnitt.
- When: Schüler ruft `GET /api/learning/materials/{material_id}/download-url?disposition=inline`.
- Then: 200 mit kurzlebiger signierter URL; UI kann `<img>`/`<iframe>` verwenden.

4) Submissions: Text (Happy Path)
- Given: Aufgabe erlaubt weitere Versuche (`max_attempts` null oder > aktueller Versuch); Abschnitt ist freigegeben.
- When: `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` mit `{ kind: 'text', text_body: '...' }`.
- Then: 201 mit Submission `{ attempt_nr, created_at, analysis_status='completed', feedback_md }`.

5) Submissions: Bild (Happy Path)
- Given: Gültiger Upload‑Intent (`image/jpeg|png`, ≤10 MB), Abschnitt freigegeben.
- When: `POST /api/learning/submissions/finalize` (prüft SHA‑256) und anschließend `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` mit `{ kind: 'image', intent_id, sha256 }`.
- Then: 201 mit Submission; Feedback wie oben.

6) Versuchslimit eingehalten (Edge)
- Given: Aufgabe `max_attempts = 2`; Schüler hat 2 Abgaben.
- When: Schüler versucht eine dritte Abgabe anzulegen.
- Then: 400 mit `detail: max_attempts_exceeded`.

7) Nicht Mitglied (Fehlerfall)
- Given: Schüler ist nicht Mitglied im Kurs.
- When: Schüler ruft Sections‑Feed oder Submission‑Create auf.
- Then: 403 `forbidden`.

8) Abschnitt nicht freigegeben (Fehlerfall)
- Given: Schüler ist Mitglied; Abschnitt/Task ist (noch) nicht freigegeben.
- When: Schüler versucht Material‑URL oder Submission anzulegen.
- Then: 404 `not_found` (keine Existenz‑Leaks).

9) Upload‑Validierung (Edge)
- Given: Upload‑Intent mit `mime_type='application/zip'` oder `size_bytes > 10MB`.
- When: Intent erzeugen.
- Then: 400 `invalid_file_type` bzw. `file_too_large`.

10) Historie abrufen (Happy Path)
- Given: Mehrere Abgaben vorhanden.
- When: `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions`.
- Then: 200 mit chronologisch sortierter Liste (älteste → neueste) oder parametrisierbar.

11) Idempotenz beim Erstellen (Stabil bei Retries)
- Given: Netzwerkaussetzer nach dem Abschicken; der Client wiederholt die Anfrage mit dem selben `Idempotency-Key`.
- When: Zweiter `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` mit identischem Header‑Wert.
- Then: 201 mit derselben `Submission` (keine Doppelanlage).

12) Ungültige IDs (Fehlerfall)
- Given: Falsch formatiertes `course_id` oder `task_id`.
- When: Beliebiger Learning‑Endpoint wird aufgerufen.
- Then: 400 `bad_request` mit `detail: invalid_uuid`.

## API‑Vertrag (Entwurf, Contract‑First Leitplanken)
- `GET /api/learning/courses/{course_id}/sections?include=materials,tasks&limit&offset`
  - Liefert nur freigegebene Abschnitte des Kurses für den eingeloggten Schüler. 200 `[SectionWithItems]`, 403/404/401.
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.
- `GET /api/learning/materials/{material_id}/download-url?disposition=inline|attachment`
  - Signierte kurzlebige URL, nur wenn Material in einem freigegebenen Abschnitt eines belegten Kurses liegt. 200 `{ url, expires_at }`.
- `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit&offset`
  - Eigene Submissions zum Task im Kurskontext. 200 `[Submission]`.
  - Pagination: `limit [1..100] (default 50)`, `offset ≥ 0`.
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`
  - Body Text: `{ kind: 'text', text_body }`; Bild: `{ kind: 'image', intent_id, sha256 }`.
  - Optional Header: `Idempotency-Key: <token[≤64]>` (mehrfache Retries ohne Doppelanlage; gleiche Antwort).
  - Responses: 201 `Submission` (MVP synchron, `analysis_status='completed'`), alternativ 202 (Async‑Flag aktiv), 400/401/403/404.
- `POST /api/learning/submissions/upload-intents`
  - Body `{ filename, mime_type ('image/jpeg'|'image/png'), size_bytes ≤ 10MB }` → 201 `{ intent_id, url, fields, max_size_bytes, expires_at }`.
- `POST /api/learning/submissions/finalize`
  - Body `{ intent_id, sha256 }` → 200 `{ intent_id, storage_key, sha256 }`.
  - Orphan‑Cleanup: Intents besitzen TTL; abgelaufene/nie finalisierte Intents werden periodisch entsorgt (Dokumentation + Worker optional).
- `GET /api/learning/submissions/{submission_id}/feedback`
  - 200 `{ analysis_json, feedback_md, analysis_status }` (MVP: completed), 404/403/401.

DTO „LerninhaltFuerLernprozessDTO“ (aus Unterrichten an Lernen):
- Kursbezug: `course_id`, `module_id`.
- Abschnitte (freigegeben): `[{ section { id, title, position }, materials[], tasks[] }]`.
- Materials: Markdown `{ id, kind='markdown', title, body_md }`; Datei `{ id, kind='file', title, mime_type, size_bytes?, filename_original? }`.
- Tasks: `{ id, instruction_md, criteria[], hints_md?, due_at?, max_attempts? }`.
- Keine internen Schlüssel oder PII.

## Datenbank / Migration (Entwurf)
Neue Tabelle `public.learning_submissions`:
```sql
create table if not exists public.learning_submissions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  student_sub text not null,
  kind text not null check (kind in ('text','image')),
  text_body text null,
  storage_key text null,
  mime_type text null,
  size_bytes integer null check (size_bytes is null or size_bytes > 0),
  sha256 text null check (sha256 ~ '^[0-9a-f]{64}$'),
  attempt_nr integer not null,
  analysis_status text not null default 'pending' check (analysis_status in ('pending','completed','error')),
  analysis_json jsonb null,
  feedback_md text null,
  error_code text null,
  created_at timestamptz not null default now(),
  completed_at timestamptz null,
  unique (course_id, task_id, student_sub, attempt_nr)
);
```
Integritäts‑Trigger/Checks (Skizze):
- `attempt_nr` wird atomar je `(course_id, task_id, student_sub)` vergeben:
  - Advisory‑Lock: `select pg_advisory_xact_lock(hash_course_task_student(course_id, task_id, student_sub));`
  - Danach `attempt_nr = coalesce(max(attempt_nr),0)+1` in derselben Transaktion.
  - Alternativ (später): dedizierte Zähler‑Tabelle.
- Guard‑Funktion `public.check_task_visible_to_student(sub text, course_id uuid, task_id uuid) returns boolean` (SECURITY DEFINER, `set search_path = public, pg_temp`) prüft Mitgliedschaft + Release‑Kette:
  `course_memberships (sub) ∧ course_modules(course_id) ∧ unit_sections(section_id) ∧ module_section_releases(visible) ∧ unit_tasks(section_id)`.
- RLS: `enable row level security;` Policies
  - SELECT/UPDATE/DELETE: `student_sub = current_setting('app.current_sub', true)` (Update/Delete praktisch nie; Submissions unveränderlich – nur Leserecht benötigt).
  - INSERT: obiger Guard (`check_task_visible_to_student`) + `max_attempts`‑Prüfung (via Join `unit_tasks.max_attempts`).

Optional: View `public.view_released_section_items_for_student(course_id, sub)` bündelt freigegebene Materials/Tasks.

Weitere Indizes & Felder:
- Zusätzlicher Index für häufige Abfragen: `(student_sub, task_id, created_at)`.
- `error_code`: kontrollierte Werte (z. B. `model_unavailable`, `ocr_failed`, `policy_violation`) für eindeutige Fehlerbehandlung.

## Architektur
- Web‑Adapter: `backend/web/routes/learning.py` (JSON API). Keine Businesslogik in den Routen.
- Repo (DB): `backend/learning/repo_db.py` (psycopg3), setzt `SET LOCAL app.current_sub`.
- Use Cases: `backend/learning/usecases/*.py` (framework‑frei), orchestrieren Submission‑Erstellung und Analyse‑Adapter.
- Analyse‑Adapter: `backend/learning/analysis_adapter.py` (MVP: synchroner Stub; später DSPy/Ollama/vllm/llama.cpp/lemonade, synchron oder asynchron).
- OCR‑Adapter: `backend/learning/ocr_adapter.py` (MVP: einfache Validierung/No‑Op; später echtes Handschrift‑/OCR‑Modell optional).

## Sicherheit
- 401 nicht angemeldet; 403 kein Kursmitglied; 404 für nicht freigegebene/fremde Ressourcen.
- Presigned URLs: kurze TTL (2–5 Min.), `disposition=inline|attachment`, strikte MIME‑Whitelist; keine PII in Query‑Parametern.
- Dateien: Bilder `image/jpeg|png`, max. 10 MB; SHA‑256 wird bei Finalize überprüft.
- Markdown‑Sanitizing: `body_md`/`feedback_md` werden sicher zu HTML gerendert (keine unsichere Inline‑HTML‑Übernahme; Sanitizer aktiv), um XSS zu verhindern.
- HTTP‑Header (Learning‑API/Frontend): `Cache-Control: private, max-age=0`, `Referrer-Policy: no-referrer`; CSP im Frontend strikt (`img-src`/`frame-src` nur eigene Domains/Storage‑Domain, `object-src 'none'`).
- Logging: Presigned‑URL‑Querystrings werden nicht geloggt.

## Tests (TDD‑Plan)
- Contract‑Tests für jeden Endpoint (pytest), inkl. 401/403/404/400 Pfade.
- DB‑Tests für RLS: nur eigene Submissions sichtbar; Release‑Gates verhindern Fremdzugriffe.
- Upload‑Flow: Intent→Upload (mock)→Finalize→Submission (image) mit Hash‑Validierung.
- Attempt‑Limit: Erreichen des Limits erzeugt 400 `max_attempts_exceeded`.
- KI‑Stub: Deterministisches Verhalten (gleicher Input → gleiches Feedback), damit Tests stabil sind; spätere Adapter werden über Contract‑Tests abgedeckt.

## Milestones
1) Schema + RLS + Helper‑Funktionen (Migrationen) – grün durch DB‑Tests.
2) Read‑API (Sections‑Feed, Material‑URL) – grün durch Contract‑Tests.
3) Create‑API (Submissions Text/Bild, Attempt‑Limit) – grün; Analyse‑Stub integriert.
4) Historie/Feedback‑Abruf – grün; End‑to‑End Smoke.

## Asynchronisierung (Iteration, Feature‑Flag)
Ziel: Ohne Umbauten am MVP auf asynchrones Feedback umschalten können, falls Modelle länger rechnen.

- API‑Oberfläche
  - `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`
    - Synchron (MVP): 201 + `Submission` mit `analysis_status="completed"`.
    - Asynchron: 202 Accepted, `Location: /api/learning/submissions/{id}`, Body enthält `Submission` mit `analysis_status="pending"`. Optional `Retry-After: 2`.
    - Optional Idempotenz: `Idempotency-Key` (Header) zur Duplikat‑Vermeidung bei Retries.
  - `GET /api/learning/submissions/{submission_id}`
    - Polling: liefert `pending|processing|completed|error` und bei Fertigstellung `feedback_md/analysis_json`.
  - `GET /api/learning/submissions/{submission_id}/feedback`
    - Shortcut‑Antwort nur mit Analysefeldern; gleiches Status‑Verhalten.
  - Optional (später): `GET /api/learning/submissions/{submission_id}/events` (SSE) für Live‑Updates als Alternative zu Polling.

- Ablauf
  - Text: Submission → Job „analysis“ → 202 `pending` → Worker verarbeitet → `completed` (+Feedback).
  - Bild: Finalize → Submission → Job „ocr“ → OCR‑Text → Folgejob „analysis“ → `completed`.
  - UI: Hinweis „Feedback wird erstellt…“, Polling‑Backoff (0.5s → 1s → 2s, max. ~30s), danach Hinweis „Später erneut prüfen“.

- Datenmodell (zusätzlich)
  - `public.learning_analysis_jobs`: `id uuid pk, submission_id uuid fk, kind text in ('ocr','analysis'), status text in ('queued','processing','completed','error'), attempts int, ready_at, started_at, finished_at, last_error text`.
  - Indizes: `(status, ready_at)`, `(submission_id)`.

- Worker & Queue (KISS)
  - Claim‑Query: `... for update skip locked limit N` auf `learning_analysis_jobs`.
  - Statusübergänge: `queued → processing → completed|error`; transiente Fehler: Backoff (1m, 3m, 10m), `attempts+=1`, zurück nach `queued`.
  - Deployment: Separater Prozess/Container (Docker Compose), Service‑DSN; keine externe Queue nötig.

- Fehler & Wiederholungen
  - Transient: Retry mit exponentiellem Backoff, max. Versuche (z. B. 5).
  - Fatal: `status='error'`, `last_error` gesetzt; UI zeigt Fehler, neue Abgabe möglich (Limit beachten).
  - API‑Poll: immer 200 mit Statusfeld; keine flackernden 5xx im UI.

- Sicherheit
  - Jobs nur für Service sichtbar (RLS/POLICIES: SELECT/UPDATE ausschließlich via SECURITY DEFINER/Service‑Role).
  - Schüler sehen nur eigene Submissions und deren Status/Feedback.
  - OCR/Analyse isoliert (Container/Netzwerk), Presigned‑URLs kurze TTL, keine PII in Query‑Params.

- Leistung & Backpressure
  - Konfiguration: Max. Parallelität, Timeout je Job, Queue‑Länge, Größenlimits bleiben (10 MB Bild).
  - Dedizierte OCR/Analyse‑Pools später möglich; Start: 1 Worker mit sequentieller Abarbeitung.

- Beobachtbarkeit
  - Metriken: Jobdauer, Erfolgsquote, Fehlercodes; Logs pro Job.
  - Submission `completed_at` konsistent pflegen; spätere Auswertung im Diagnostik‑Kontext.

- Migrationen (Skizze)
  - `20251024121001_learning_submissions.sql` (MVP Submissions)
  - `20251024121005_learning_jobs.sql` (Jobs + Indizes)
  - `20251024121006_learning_jobs_rls.sql` (Policies/SECURITY DEFINER)
  - Optional: `20251024121007_learning_job_triggers.sql` (automatisch Job bei Submission anlegen)

- Tests
  - API‑Contract: 202‑Pfad, `Location`/`Retry-After`, Polling bis `completed`.
  - Worker: Unit‑Tests für Claim/Retry/Backoff; Integration mit deterministischem OCR/Analyse‑Mock.
- RLS: Schüler‑Isolation bleibt gewahrt; Jobs nicht lesbar für Schüler.

## Roadmap & Batches (Iterativ, testgetrieben)

Batch 1 — Schema & RLS (DB‑First)
- Migration `learning_submissions` inkl. Indizes, Constraints, RLS (SELECT self‑only, INSERT Guard).
- Helper: `check_task_visible_to_student` (SECURITY DEFINER, gehärteter `search_path`), `next_attempt_nr` (Advisory‑Lock).
- DB‑Tests (pytest + echte Test‑DB) für RLS/Guards/Attempt‑Vergabe.

Batch 2 — Read‑API (Sections/Materials)
- `GET /api/learning/courses/{course_id}/sections?include=materials,tasks&limit&offset`.
- `GET /api/learning/materials/{material_id}/download-url?disposition=`.
- Contract‑Tests 401/403/404/200, Pagination‑Caps.

Batch 3 — Submissions (Text, synchron)
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions` (Text), KI‑Stub synchron (deterministisch).
- `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit&offset` (History).
- Attempt‑Limit + Idempotency‑Key Tests.

Batch 4 — Upload‑Flow (Image)
- Upload‑Intents (Whitelist/Size), Finalize (SHA‑256) + Image‑Submission.
- Orphan‑Intent TTL/Docs, Tests für Hash‑Mismatch & Limits.

Batch 5 — Async (optional, Flag)
- 202‑Variante + `GET /api/learning/submissions/{submission_id}` (Polling) + Backoff‑Empfehlungen.
- Einfache Jobs‑Tabelle + Worker‑Claim‑Loop (optional).

Batch 6 — Observability & Hardening
- Metriken, strukturierte Fehlercodes, Rate‑Limits/Headers, CSP‑Checkliste validieren.

Hinweise
- Jede Änderung startet im `api/openapi.yml` (Contract‑First) und wird testgetrieben implementiert.
- Glossar‑Begriffe konsistent halten (Submission/Task/Release, `sub` ohne PII).
