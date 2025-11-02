# Plan: KI-Integration (OCR + Feedback) — Lernen

Ziel: Zwei KI-Funktionen sauber, testgetrieben und DSGVO‑konform integrieren:
1) OCR: Extrahiert Text aus Bild- und PDF‑Abgaben (image/file) und speichert ihn in `text_body` der Submission.
2) Feedback: Generiert formatives Feedback zu jeder Submission (text/image/file) auf Basis der Aufgaben‑Kriterien (`criteria`).

Leitplanken: KISS, Security first, FOSS, Clean Architecture, Contract‑First (OpenAPI), Test‑First (TDD, Red‑Green‑Refactor), Glossar‑Konsistenz (`docs/glossary.md`).

Begriffe (Glossar-konsistent): Submission, Task, Criteria, OCR, Analysis, Feedback, `student_sub` (OIDC sub, ohne PII).

---

## Scope & Nicht‑Ziele

In Scope (Iteration 1, asynchron, lokal):
- OCR (Bild: JPEG/PNG; Datei: PDF) mit lokalem Backend (Ollama/DSPy) — keine Cloud.
- Feedback-Generierung über denselben lokalen Stack (Stub zunächst, später DSPy/Ollama), deterministisch testbar.
- `text_body` ist die kanonische Quelle für alle Arten von Submissions (auch nach OCR).
- Asynchroner Verarbeitungs-Flow: HTTP-Endpunkt speichert Submission mit `analysis_status=pending`, Worker verarbeitet OCR + Feedback und markiert Submission als `completed` oder `failed`.

Nicht in Scope (Iteration 1):
- Externe KI-Dienste, Cloud-APIs oder Datentransfer außerhalb der lokalen Infrastruktur.
- Fortgeschrittene Rubrics/Mehrsprachigkeit, komplexe Metriken.

---

## User Stories (validiert)
- Als Schüler reiche ich Bild/PDF ein; das System extrahiert Text (OCR) und speichert ihn so, als hätte ich Text eingetippt, damit Feedback einheitlich möglich ist.
- Als Schüler reiche ich Text ein; das System analysiert nach Kriterien und gibt mir formative Rückmeldung.
- Als Schüler sehe ich pro Abgabe Status, verwendeten Text (getippt oder OCR) und Feedback zur Selbstreflexion.
- Als Lehrer will ich, dass OCR/Feedback lokal (Ollama/DSPy), DSGVO‑konform, mit Zeitlimits und minimalen Logs laufen.

---

## BDD‑Szenarien (Given‑When‑Then)

Happy Path
1) Text‑Submission erzeugt sofort Feedback
- Given: Aufgabe ist freigegeben, Schüler ist Mitglied, `max_attempts` erlaubt neuen Versuch
- When: POST Submissions mit `{ kind: 'text', text_body: '...' }`
- Then: 201, `analysis_status='completed'`, `text_body`=übergebener Text, `feedback` gesetzt, `attempt_nr` korrekt

2) Bild‑Submission (JPEG/PNG) mit asynchronem OCR
- Given: Gültige Metadaten (`mime_type`, `size_bytes` ≤ 10 MiB, `sha256`), Abschnitt freigegeben
- When: POST Submissions mit `{ kind: 'image', storage_key, mime_type, size_bytes, sha256 }`
- Then: 202, `analysis_status='pending'`, `text_body` leer, `analysis_json` leer, Worker-Job existiert
- And: Wenn der Worker erfolgreich abschließt, `analysis_status`→`completed`, `text_body`=OCR‑Ergebnis, `feedback` gesetzt

3) PDF‑Submission mit asynchronem OCR
- Given: Gültige Metadaten (`mime_type='application/pdf'`, ≤ 10 MiB)
- When: POST Submissions mit `{ kind: 'file', ... }`
- Then: 202, `analysis_status='pending'`, Worker-Job geplant
- And: Nach Worker-Lauf wie oben `completed` mit OCR‑Text und Feedback

Edge Cases
4) Maximalversuche
- Given: `max_attempts = 2`, Schüler hat 2 Abgaben
- When: POST dritte Abgabe
- Then: 400, `detail: max_attempts_exceeded`

5) Idempotency
- Given: Wiederholung mit gleichem `Idempotency-Key`
- When: POST erneut
- Then: 201/200 äquivalent mit identischer Submission (keine Duplikate)

6) Größe/MIME invalid
- Given: Datei > 10 MiB oder `mime_type` nicht erlaubt
- When: POST
- Then: 400, `detail: invalid_image_payload | invalid_file_payload`

Fehlerfälle
7) Nicht Mitglied
- Given: Schüler ist nicht Mitglied
- When: POST Submission
- Then: 403

8) Abschnitt/Task nicht freigegeben
- Given: Mitglied, aber Task nicht sichtbar
- When: POST Submission
- Then: 404

9) Worker markiert OCR‑Fehler
- Given: OCR-Adapter wirft dauerhaften Fehler (nach Retries)
- When: Worker verarbeitet Submission
- Then: Submission `analysis_status='failed'`, `error_code='ocr_failed'`, `ocr_last_error` befüllt, `text_body` bleibt leer

10) Worker markiert Analyse‑Fehler
- Given: Feedback-Adapter schlägt fehl
- When: Worker verarbeitet Submission
- Then: Submission `analysis_status='failed'`, `error_code='analysis_failed'`, Audit-Log geschrieben

11) Retry bis Erfolg
- Given: OCR-Adapter ist beim ersten Versuch nicht erreichbar
- When: Worker führt den Job aus, erster Versuch scheitert (transient)
- Then: Job wird erneut eingeplant; beim zweiten Versuch gelingt OCR → Submission `analysis_status='completed'`
---

## Architektur & Adapter

Prinzip: Clean Architecture. Use Cases kennen keine Web‑ oder Modell‑Details. KI wird über Ports injiziert.

Ports (Domain‑nah):
- `SubmissionStoragePort` (Presign, Verify, optional Download-Stream für lokalen OCR-Dienst)
- `LearningSubmissionQueuePort` (enqueue, lease, ack, retry Jobs)
- `OcrAdapterProtocol` (`extract_text(storage_key, mime_type, *, sha256) -> str`)
- `FeedbackAdapterProtocol` (`analyze(criteria, text_body) -> dict`)

Flow:
1. HTTP-Layer validiert Request, ruft Use Case `IngestLearningSubmission`.
2. Use Case führt Autorisierungs-Checks aus, verifiziert Upload, persistiert Submission mit `analysis_status='pending'` und legt den Job über `LearningSubmissionQueuePort` an.
3. Worker `process_learning_submission_ocr_jobs` leased Jobs, streamt Datei lokal zu Ollama-OCR, holt Text, ruft Feedback-Adapter, aktualisiert Submission (`analysis_status='completed'`, `text_body`, `analysis_json`, `feedback_md`) oder markiert `failed`.
4. Fehlerbehandlung: Retries (max. 3, exponential backoff). Bei dauerhaften Fehlern setzt Worker `error_code` (`ocr_failed`, `analysis_failed`) und persistiert `ocr_last_error`.

Implementierungen:
- `StubOcrAdapter` und `StubFeedbackAdapter` für Tests/Entwicklung (deterministisch, schnell).
- `LocalOcrAdapter` (Ollama Vision über DSPy) und `LocalFeedbackAdapter` (Ollama Textmodell) für Produktion; beide laufen auf demselben Server (keine Cloud).
- Queue-Port kann initial auf PostgreSQL-gestützte Tabelle (`learning_submission_ocr_jobs`) oder Supabase-Queue abbilden.

Security/Privacy:
- KI läuft lokal via Ollama; Kommunikation passiert ausschließlich über Unix-Socket/localhost.
- Timeouts (z. B. 30s OCR, 15s Feedback) und Ressourcen-Limits verhindern Hänger; Job wird andernfalls als `failed` protokolliert.
- Minimale Logs: keine Rohbilder/Texte in Logfiles, nur Hash/IDs/Timing. Audit-Log speichert Fehlercodes ohne personenbezogene Daten.
- RLS unverändert (Insert-Guard; kein Datenleck über Fehlermeldungen/IDs).

---

## API Contract‑Änderungen (OpenAPI Entwurf)

Aktueller Contract deckt Submissions bereits ab. Anpassungen:
- `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions`: Beschreibung + Responses ergänzen (`201` für Text, `202` für image/file mit Pending-Status).
- Schema `LearningSubmission.analysis_status`: erlaubte Werte `pending`, `completed`, `failed`.
- Schema `LearningSubmission.error_code`: optional, Werte `ocr_failed`, `analysis_failed`, `ocr_retrying` (für Monitoring).
- `GET /api/learning/submissions/{id}` dokumentiert Polling auf dem gleichen Statusmodell (kein neues Flag nötig).

Beispiel‑Snippet:
```yaml
components:
  schemas:
    LearningSubmission:
      properties:
        analysis_status:
          type: string
          enum: [pending, completed, failed]
          description: Pending bedeutet OCR/Feedback läuft im Hintergrund.
        error_code:
          type: string
          nullable: true
          description: One of: ocr_failed, analysis_failed, ocr_retrying.
        text_body:
          type: string
          nullable: true
          description: Schülertext oder OCR-Text; bei pending/failed kann leer sein.
paths:
  /api/learning/courses/{course_id}/tasks/{task_id}/submissions:
    post:
      responses:
        '201':
          description: Submission erstellt (kind=text), Analyse abgeschlossen.
        '202':
          description: Submission angenommen (kind=image|file), Analyse pending.
```

---

## Datenbank‑Änderungen (SQL‑Migration Entwurf)

Problem: Bisherige Constraints verhindern gefülltes `text_body` für Bilder und es fehlen Felder für Pending-/Failed-States sowie die Job-Queue.

Migration (Skizze):
```sql
set search_path = public, pg_temp;

-- 1) Constraints für image/file anpassen (text_body optional, aber Metadaten verpflichtend)
alter table public.learning_submissions drop constraint if exists learning_submissions_image_kind;
alter table public.learning_submissions add constraint learning_submissions_image_kind
  check (
    kind <> 'image' or (
      storage_key is not null and
      mime_type in ('image/jpeg','image/png') and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

alter table public.learning_submissions drop constraint if exists learning_submissions_file_kind;
alter table public.learning_submissions add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type = 'application/pdf' and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

-- 2) Analyse-Status auf pending/completed/failed einschränken
alter table public.learning_submissions drop constraint if exists learning_submissions_analysis_status_check;
alter table public.learning_submissions add constraint learning_submissions_analysis_status_check
  check (analysis_status in ('pending','completed','failed'));

-- 3) OCR-Metadaten für Worker-Retries
alter table public.learning_submissions
  add column if not exists ocr_attempts integer not null default 0,
  add column if not exists ocr_last_error text,
  add column if not exists ocr_last_attempt_at timestamptz;

-- 4) Job-Queue für Worker (FIFO, lokal)
create table if not exists public.learning_submission_ocr_jobs (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.learning_submissions(id) on delete cascade,
  payload jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  retry_count integer not null default 0,
  visible_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists learning_submission_ocr_jobs_visible_idx
  on public.learning_submission_ocr_jobs (visible_at) where status = 'queued';
```

RLS/Grants: Insert/Select bleiben; Worker-Updates erfolgen über `SECURITY DEFINER`-Function, die nur Pending→Completed/Failed erlaubt.

---

## Teststrategie (TDD)

Kontext: `pytest` gegen echte Test‑DB; externe Abhängigkeiten (OCR/Feedback) werden gemockt.

Tests (erste rote Tests):
1) `test_post_text_submission_returns_completed_feedback`
   - Erwartet 201, `analysis_status='completed'`, deterministisches Feedback.
2) `test_post_image_submission_returns_pending_and_enqueues_job`
   - Erwartet 202, `analysis_status='pending'`, Queue enthält Job mit Submission-ID.
3) `test_worker_processes_pending_submission_to_completed`
   - Worker holt Job, OCR/Feedback-Adapter (gemockt) liefern Ergebnis → Submission `analysis_status='completed'`, `text_body`/`analysis_json`/`feedback_md` gesetzt.
4) `test_worker_marks_submission_failed_after_retry_limit`
   - OCR-Adapter wirft Fehler, Worker versucht dreimal, danach `analysis_status='failed'`, `error_code='ocr_failed'`, `ocr_last_error` gesetzt.
5) `test_invalid_mime_or_size_rejected`
   - 400, dokumentierte Fehlerdetails.
6) `test_max_attempts_enforced`
   - 400, `detail='max_attempts_exceeded'`.
7) `test_idempotent_submission_returns_existing_row`
   - Wiederholter POST (gleiches Idempotency-Key) liefert die vorhandene Submission (Status unverändert).

Muster: Red → minimale Implementierung → Green → Refactor (Ports klar trennen, Worker entkoppeln).

---

## Schrittweiser Umbau (Implementierungsskizze)

Iteration 1 (asynchron, lokal):
1) OpenAPI-Beschreibung aktualisieren (201/202, Pending-Status, Fehlercodes).
2) Migration fahren (Constraints, Status-Enum, OCR-Metadaten, Job-Tabelle).
3) Use Case `IngestLearningSubmission` implementieren (Ports injizieren, Pending persistieren, Job enqueuen).
4) Worker-Service `process_learning_submission_ocr_jobs` erstellen (Stub-Adapter, Retry-Strategie, Completed/Failed-Updates).
5) Repository-Schicht anpassen (Pending-Insert, Status-Updates, Queue-Operationen, Audit-Logging).
6) Tests grün machen (API + Worker + Repo) mit Stub-Adaptern und echter Test-DB.

Iteration 1b:
7) Lokale Ollama/DSPy-Adapter produktiv schalten (konfigurierbar via `AI_BACKEND=stub|local`), Ressourcen-Limits dokumentieren.
8) Monitoring & Observability (Metriken `ocr_jobs_inflight`, `ai_worker_retry_total`, strukturierte Logs).

---

## Security & DSGVO
- Lokale Inferenz (Ollama) auf dedizierter Maschine/Container; kein Transport zu Drittanbietern.
- Minimal-Logging: keine Rohbilder/ganzen Texte im Log; nur Hash, Submission-ID, Laufzeit, Statuswechsel.
- Worker läuft unter Service-Account mit minimalen Rechten; Updates erfolgen über `SECURITY DEFINER`-Function (nur Pending→Completed/Failed).
- Timeouts, Ressourcen-Limits (10 MiB, MIME-Whitelist, CPU/GPU-Limits) verhindern Missbrauch und DoS.
- RLS bleibt Dreh- und Angelpunkt (Insert-Guard, `app.current_sub`), Worker authentifiziert sich über Service Key.
- CSRF-Check wie im Contract dokumentiert (same-origin Pflicht bei POST); Idempotency-Key Pflicht für wiederholte Requests.

---

## Observability
- Strukturierte Statuswechsel (`pending` → `completed|failed`) mit `error_code` (`ocr_failed`, `analysis_failed`, `ocr_retrying`).
- Metriken: `ocr_jobs_inflight`, `ai_worker_duration_seconds`, `ai_worker_retry_total`, `ai_worker_failed_total`.
- Logs: Jeder Jobwechsel (enqueue, lease, success, retry, fail) als strukturierter Eintrag ohne Rohdaten.
- Alerts: `ai_worker_failed_total` und `ocr_jobs_inflight` > Threshold.

---

## Risiken & Gegenmaßnahmen
- Worker-Stau: Monitoring + Auto-Scaling (mehr Worker-Instanzen) oder Priorisierung.
- Ressourcen (GPU/CPU): Fallback auf Stub/leichteres Modell; Feature-Flag `AI_BACKEND`.
- Konsistenz: Pending→Completed-Updates ausschließlich über Repository-Funktionen mit Transaktionen.
- Fehlerhafte Modelle: Retries + `failed`-Status mit Audit-Log; Operator kann Submission erneut triggern.

---

## Offene Fragen
- Welche lokalen Modelle bevorzugen wir initial (z. B. qwen2.5‑vl vs. gemma3 vision)?
- Gewünschte maximale Wartezeit (Timeout) aus UX‑Sicht?
- Benötigen Lehrkräfte Einsicht in OCR‑Qualität (z. B. Konfidenz)?

---

## Befehle & Workflow
- Contract‑First: `api/openapi.yml` anpassen
- Migration: `supabase migration new`, `supabase migration up`
- Tests: `.venv/bin/pytest -q`
- Lokal stacken: `docker compose up -d --build`, `supabase status`

---

## Quellen & Legacy‑Bezug
- Alpha2 Stub: `backend/learning/repo_db.py` (Analyse‑Platzhalter)
- Legacy (Alpha1) Vision: `legacy-code-alpha1/app/ai/vision_processor.py` (DSPy+Ollama)
- Glossar: `docs/glossary.md`
