# Learning AI — Reference

Purpose: Explain how GUSTAV processes learning submissions with local AI (OCR + formative feedback) while keeping the Learning bounded context consistent with Clean Architecture, KISS, and security-first principles.

This document complements `docs/references/learning.md`. It describes the AI-specific ports, adapters, worker lifecycle, observability, and operational requirements. For API contracts and student-facing behaviour see the Learning reference file.

---

## 1. Purpose & Scope
- **OCR**: Extract handwritten or printed text from image/PDF submissions and populate `text_body`.
- **Feedback**: Generate formative feedback based on task criteria using the same `text_body` (typed or OCR).
- **Local only**: All inference happens on self-managed Ollama/DSPy instances; no third-party cloud calls.
- **Async-first**: Submissions with `kind=image|file` return `202` with `analysis_status=pending`. A worker processes vision (OCR) + feedback and updates the submission to `completed` or `failed`.

Out of scope here: Teaching-side workflows, UI specifics, detailed task modelling.

---

## 2. Architecture Overview
1. **HTTP Layer** validates request & permissions, calls the use case `IngestLearningSubmission`.
2. **Use Case** stores the submission with `analysis_status=pending` (für text/image/file) und enqueued einen Job über den Queue‑Port. Ein späterer optionaler Fast‑Path (201) ist vertraglich dokumentiert, aktuell aber deaktiviert.
3. **Worker** (`process_learning_submission_jobs`) leases jobs FIFO, streams the file to the local OCR adapter, runs feedback analysis, persists results, and emits follow-up events.
4. **Persistence** is guarded by repository functions and RLS. Worker updates go through a `SECURITY DEFINER` function to mutate `analysis_status`, `analysis_json`, `feedback_md`.
5. **Observability**: Structured logs, metrics (`analysis_jobs_inflight`, `ai_worker_failed_total`), alerts (adapter failures, queue backlog).

---

## 3. Ports & Adapter Contracts

| Port / Adapter | Signature (Python typing) | Responsibility | Security Notes |
| --- | --- | --- | --- |
| `SubmissionStoragePort` | ```python\nclass SubmissionStoragePort(Protocol):\n    def create_presign(self, *, course_id: UUID, task_id: UUID, student_sub: str,\n                       mime_type: str, size_bytes: int) -> PresignResult: ...\n    def verify_object(self, *, storage_key: str, sha256: str,\n                      size_bytes: int) -> StorageVerifyResult: ...\n    def stream_to_local_tmp(self, *, storage_key: str) -> Iterator[bytes]: ...\n``` | Generate presigned URLs, verify uploaded objects (HEAD), optionally stream content for local OCR. | Runs server-side with service credentials; ensures namespacing `submissions/{course}/{task}/{student}/...`. |
| `LearningSubmissionQueuePort` | ```python\nclass LearningSubmissionQueuePort(Protocol):\n    def enqueue(self, job: SubmissionJobPayload) -> None: ...\n    def lease_next(self, *, now: datetime) -> Optional[QueuedJob]: ...\n    def ack(self, job_id: UUID) -> None: ...\n    def retry_later(self, job_id: UUID, *, visible_at: datetime) -> None: ...\n``` | Abstract queue backed by PostgreSQL table `learning_submission_jobs`. | Applies per-tenant isolation; only worker role can lease/ack jobs. |
| `OcrAdapterProtocol` | ```python\nclass OcrAdapterProtocol(Protocol):\n    def extract_text(self, *, storage_key: str, mime_type: str,\n                     sha256: str, data_stream: Iterable[bytes]) -> str: ...\n``` | Feed file bytes into local OCR (Ollama Vision via DSPy) and return normalized text. | Must enforce MIME whitelist, size limits, timeouts (≤30s), no external calls. |
| `FeedbackAdapterProtocol` | ```python\nclass FeedbackAdapterProtocol(Protocol):\n    def analyze(self, *, criteria: Sequence[str],\n                submission_text: str) -> FeedbackResult: ...\n``` | Produce deterministic formative feedback (scores, markdown message). | Uses local Ollama text model; no network access; logs only model/runtime metadata. |
| `LearningSubmissionEventPort` (optional) | ```python\nclass LearningSubmissionEventPort(Protocol):\n    def emit_ocr_requested(self, payload: OCRRequestedEvent) -> None: ...\n    def emit_analysis_completed(self, payload: AnalysisCompletedEvent) -> None: ...\n``` | Publish domain events for downstream analytics dashboards. | Events carry IDs/metadata but never raw student content. |

Stub implementations exist for tests (`StubOcrAdapter`, `StubFeedbackAdapter`, in-memory queue). Production adapters wrap Ollama/DSPy with resource guards.

---

## 4. Worker Lifecycle & Status Mapping

### Job Table
- `public.learning_submission_jobs` columns:
- `status`: `queued` → `leased` → (`failed` | delete on success)
  - `retry_count`, `visible_at`: used for exponential backoff (e.g. 5s, 15s, 45s)
  - `payload`: JSON with `submission_id`, `storage_key`, `mime_type`, `sha256`, `student_sub`

### Processing Flow
1. Worker leases the earliest `visible_at <= now` job.
2. Sets `status=processing`, increments `retry_count`, updates `visible_at=now + lease_timeout`.
3. Streams file via storage port, runs OCR adapter to obtain text.
4. Runs feedback adapter with criteria + text.
5. Writes results via helper: update submission to `analysis_status='completed'`, set `text_body`, `analysis_json (criteria.v1)`, `feedback_md`, `vision_attempts`, `vision_last_attempt_at`.
6. Emits event (`LearningSubmissionAnalysisRequested`) to keep dashboard harmonised.
7. Acknowledges job (`status=completed`).

If OCR or feedback fails:
- Record error in `ocr_last_error`, increment `ocr_attempts`.
- When `retry_count < 3`, schedule retry with exponential backoff.
- Else mark submission `analysis_status='failed'`, set `error_code` (`vision_failed` or `feedback_failed`), persist final job `status=failed`, and log audit entry.

**Status semantics** (Learning submission table):
- `pending`: waiting for worker; `text_body` may be empty.
- `completed`: OCR + feedback succeeded; UI can display results.
- `failed`: Worker exhausted retries; UI should prompt student/teacher to re-upload or contact support.

---

## 5. Data Model & Migrations
- Constraints on `kind=image|file`: require `storage_key`, MIME whitelist (`image/jpeg`, `image/png`, `application/pdf`), `size_bytes ∈ [1,10 MiB]`, lowercase SHA-256.
- Added columns: `ocr_attempts`, `ocr_last_error`, `ocr_last_attempt_at`.
- `analysis_status` limited to `pending | completed | failed`.
- Job table `learning_submission_jobs` with indexes on `status, visible_at`.
- Worker updates execute via `SECURITY DEFINER` function `learning_queue_consume_job(submission_id uuid, ...)` to keep RLS intact.

Refer to the latest migration plan in `docs/plan/2025-11-01-ki-integration.md` for SQL sketches.

---

## 6. Security & Privacy
- OCR/feedback adapters run on the same network/host (localhost or Unix socket). No outbound network calls.
- Credentials (Ollama tokens, service accounts) live in the secret store (`.env.production` or container secrets).
- Logs contain identifiers (submission UUID, course/task IDs) but never raw text or images.
- Audit log entry per job (`queued`, `processing`, `completed`, `failed`) with actor `ai_worker`.
- CSRF, RLS, and idempotency enforced at HTTP layer; worker path only handles server-to-server traffic.
- Remote Supabase fetches use the service-role key and only accept URLs that match the host+port pairs defined via `SUPABASE_URL` / `SUPABASE_PUBLIC_URL`. HTTP is allowed solely for loopback or `.local` hosts; redirects and HTTP status ≥ 400 are surfaced with explicit reason codes so operators can distinguish host-mismatch vs. storage errors.
- Storage verification (`verify_storage_object_integrity`) now enforces the learning upload MIME whitelist, distinguishes `match_head` (trusted SHA header) from `match_download` (streamed fallback), and propagates redirect/untrusted-host errors so ingestion can fail fast instead of queuing corrupt files.

---

## 7. Observability & Operations

### Telemetry Surfaces
- **Student UI / API**: Shows `vision_attempts`, `vision_last_error`, `feedback_last_attempt_at`, `feedback_last_error`. Strings are sanitized server-side (secrets stripped, length ≤256) so Lernende nur den Status erkennen.
- **Teacher UI**: Enthält dieselben Felder plus Kontext (z. B. erneute Anstöße, Support-Hinweise). Rohpfade/Storage-Keys bleiben verborgen.
- **Worker Logs**: Vollständige Fehlermeldungen + Stacktraces, aber nur serverseitig abrufbar (RLS-konformes Service-Account). Nutzt dieselbe Sanitizer-Funktion bevor Inhalte persistiert werden.
- **Learning Analytics Dashboard**: Aggregiert Telemetrie (Attempts, Dauer zwischen Versuchen) für Trendanalysen; persönliche Daten werden dabei pseudonymisiert.
- **Upload Proxy**: Nutzt einen asynchronen Forwarder (httpx) und blockiert keine Event-Loop-Worker mehr; Upstream-Fehler liefern 502 in allen Umgebungen.

- **Metrics**
  - `analysis_jobs_inflight` (gauge)
  - `ai_worker_processed_total{status}` (counter)
  - `ai_worker_retry_total{phase}` (counter)
  - `ai_worker_failed_total{error_code}` (counter)
  - `ai_worker_duration_seconds` (histogram per step, follow-up)
- **Logs**
  - Strukturierte Warn-/Error-Logs bei Retries/Failures (`submission_id`, `job_id`, `next_visible_at`, `error_code`).
  - Keine Rohinhalte in Logs; nur IDs und gekürzte Fehlermeldungen.
  - Local-Vision-Adapter nutzt `_log_storage_event` für Storage-Pfade: Aktionen wie `cached_stitched`, `stitch_from_page_keys`, `fetch_remote_image`, `remote_fetch_failed reason=redirect` zeigen klar an, ob der Worker Cache, Seiten-Assets oder Remote-Fetch verwendet hat – ohne Bucket/Studentenpfade zu protokollieren.
- **Alerts**
  - `ai_worker_failed_total` spike within 5 minutes.
  - Queue backlog (> N jobs pending).
  - OCR latency > threshold.
- **Incident Response**
  - Runbook: inspect job table, review audit log, replay submission via admin endpoint (future).
  - Manual override: flag submission `failed` with operator note, notify teacher.

---

## 8. Testing Strategy
- Tests use `StubOcrAdapter` / `StubFeedbackAdapter` plus an in-memory or transactional queue fake.
- Key pytest modules:
  - API tests ensure `201/202` responses, queue enqueue, status transitions.
  - Worker tests simulate retries, failure modes, and final status updates.
  - Repository tests validate constraints, RLS, and `SECURITY DEFINER` functions.
  - Vision adapter unit tests (`backend/tests/learning_adapters/test_local_vision_model_helper.py`) sichern `_call_model` ab (Timeouts, Markdown-Unwrap, `images`-Parameter), damit der eigentliche Adapter schlank bleibt.
- For integration: spin up local Supabase + Ollama in docker compose; avoid live calls in CI (use stubs).
- Red-Green-Refactor disciplined: write failing test, implement minimal code, refactor adapters/ports.

---

## 9. Configuration & Deployment

### 9.1 Environment variables (overview)

| Name | Default | Scope | Notes |
| --- | --- | --- | --- |
| `AI_BACKEND` | `local` in `.env.example` (parser default: `stub`) | Worker DI | Selects adapter pair: `local` → `backend.learning.adapters.local_*`, `stub` → stub adapters. In prod/stage `stub` ist verboten und führt zu einem Fail-fast beim Laden der Config. |
| `LEARNING_VISION_ADAPTER` | derived from `AI_BACKEND` | Worker DI | Optional override für den Vision‑Adapter (vollqualifizierter Modulpfad). Wenn gesetzt, überschreibt er die aus `AI_BACKEND` abgeleitete Voreinstellung. |
| `LEARNING_FEEDBACK_ADAPTER` | derived from `AI_BACKEND` | Worker DI | Wie oben, aber für den Feedback‑Adapter. |
| `AI_VISION_MODEL` | `qwen2.5vl:3b` | Vision | Modellname, der an den Ollama‑Client für Vision/OCR übergeben wird. |
| `AI_FEEDBACK_MODEL` | `gpt-oss:latest` | Feedback | Modellname für den Feedback‑Pfad; wird im DSPy‑Programm als `ollama/<model>` verwendet. |
| `AI_TIMEOUT_VISION` | `30` Sekunden | Vision | Timeout (Sekunden) für Vision‑Aufrufe; `1..300`, sonst Fehler in `load_ai_config()`. |
| `AI_TIMEOUT_FEEDBACK` | `15` Sekunden | Feedback | Timeout (Sekunden) für Feedback‑Aufrufe; `1..300`, sonst Fehler. |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Vision/Feedback | Basis‑URL des lokalen Ollama‑Dienstes. `load_ai_config()` erzwingt `http://` oder `https://` und beschränkt Hosts auf `localhost`/Loopback oder einfache Servicenamen ohne Punkt (z. B. `ollama`). Der DSPy‑Pfad setzt daraus `OLLAMA_HOST`/`OLLAMA_API_BASE`. |
| `LEARNING_DSPY_JSON_ADAPTER` | `true` (siehe `.env.example` / `docker-compose.yml`) | Feedback/DSPy | Schaltet den DSPy‑`JSONAdapter` ein/aus. `true` erzwingt streng typisierte strukturierte Outputs; `false` nutzt die Standard‑LM‑Pfad ohne Adapter, toleranter gegenüber unvollständigem JSON. |
| `FEATURE_OCR_ENABLED` | nicht gesetzt/`true` (implizit) | Worker | Schaltet OCR+Queue‑Pfad insgesamt. Wenn deaktiviert, akzeptiert das System keine Bild/File‑Submissions für Vision und fällt auf reine Text‑Flows zurück. |
| `WORKER_MAX_RETRIES` | `3` | Worker | Maximale Retry‑Anzahl pro Job. |
| `WORKER_BACKOFF_SECONDS` | `10` | Worker | Basis‑Backoff (Sekunden) zwischen Retries. |
| `WORKER_LEASE_SECONDS` | `45` | Worker | Lease‑Dauer für Queue‑Jobs. |
| `WORKER_POLL_INTERVAL` | `0.5` | Worker | Poll‑Intervall für den Worker‑Loop. |
| `SUPABASE_URL`, `SUPABASE_PUBLIC_URL` | projektabhängig | Vision/Storage | Definieren die erlaubten Host:Port‑Paare für Remote‑Fetches der Vision‑Pipeline. Der Adapter akzeptiert nur URLs, deren Host+Port genau diesen Werten entsprechen (plus strenge HTTP/HTTPS‑Regeln, siehe unten). |

Zusätzliche Leitplanken:
- Vision‑Remote‑Fetch:
  - Der Adapter akzeptiert nur Hosts aus `SUPABASE_URL`/`SUPABASE_PUBLIC_URL`.
  - HTTPS ist obligatorisch; HTTP wird nur für Loopback/localhost‑Hosts akzeptiert.
  - Antworten werden gestreamt und bei Überschreitung von `LEARNING_MAX_UPLOAD_BYTES` abgebrochen (`size_exceeded`).
- DSPy/JSONAdapter:
  - `LEARNING_DSPY_JSON_ADAPTER=true` führt dazu, dass das DSPy‑Programm `dspy.JSONAdapter` konfiguriert, sodass strukturierte Ergebnisse (`criteria.v2`) strikt geparst werden.
  - Bei schwachen/instabilen Modellen kann lokal `LEARNING_DSPY_JSON_ADAPTER=false` gesetzt werden, um auf eine robustere, aber weniger strikt typisierte Pfad zurückzufallen (Parser nutzt dann interne Fallbacks).

### 9.2 Deployment notes
- Worker process:
  - Run via `poetry run python -m backend.learning.worker` or container `learning-ai-worker`.
  - Horizontal scaling allowed; locking is handled via queue `status` update with optimistic concurrency.
- Feature flags:
  - `FEATURE_OCR_ENABLED` toggles OCR+queue. When disabled, submissions fallback to text-only flow (no image/file acceptance).

---

## 10. Future Extensions
- Job prioritisation (e.g. teacher waiting in real-time).
- Additional file types (HEIC, DOCX) with dedicated adapters.
- OCR confidence scores exposed in UI.
- Asynchronous notification API / WebSocket updates for completion events.

---

## References
- Plan: `docs/plan/2025-11-01-learning-submissions-file-ocr.md`
- Plan: `docs/plan/2025-11-01-ki-integration.md`
- Legacy inspiration: `legacy-code-alpha1/app/ai/vision_processor.py`
