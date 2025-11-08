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
3. **Worker** (`process_learning_submission_ocr_jobs`) leases jobs FIFO, streams the file to the local OCR adapter, runs feedback analysis, persists results, and emits follow-up events.
4. **Persistence** is guarded by repository functions and RLS. Worker updates go through a `SECURITY DEFINER` function to mutate `analysis_status`, `analysis_json`, `feedback_md`.
5. **Observability**: Structured logs, metrics (`analysis_jobs_inflight`, `ai_worker_failed_total`), alerts (adapter failures, queue backlog).

---

## 3. Ports & Adapter Contracts

| Port / Adapter | Signature (Python typing) | Responsibility | Security Notes |
| --- | --- | --- | --- |
| `SubmissionStoragePort` | ```python\nclass SubmissionStoragePort(Protocol):\n    def create_presign(self, *, course_id: UUID, task_id: UUID, student_sub: str,\n                       mime_type: str, size_bytes: int) -> PresignResult: ...\n    def verify_object(self, *, storage_key: str, sha256: str,\n                      size_bytes: int) -> StorageVerifyResult: ...\n    def stream_to_local_tmp(self, *, storage_key: str) -> Iterator[bytes]: ...\n``` | Generate presigned URLs, verify uploaded objects (HEAD), optionally stream content for local OCR. | Runs server-side with service credentials; ensures namespacing `submissions/{course}/{task}/{student}/...`. |
| `LearningSubmissionQueuePort` | ```python\nclass LearningSubmissionQueuePort(Protocol):\n    def enqueue(self, job: SubmissionJobPayload) -> None: ...\n    def lease_next(self, *, now: datetime) -> Optional[QueuedJob]: ...\n    def ack(self, job_id: UUID) -> None: ...\n    def retry_later(self, job_id: UUID, *, visible_at: datetime) -> None: ...\n``` | Abstract queue backed by PostgreSQL table `learning_submission_ocr_jobs` (or Supabase queue). | Applies per-tenant isolation; only worker role can lease/ack jobs. |
| `OcrAdapterProtocol` | ```python\nclass OcrAdapterProtocol(Protocol):\n    def extract_text(self, *, storage_key: str, mime_type: str,\n                     sha256: str, data_stream: Iterable[bytes]) -> str: ...\n``` | Feed file bytes into local OCR (Ollama Vision via DSPy) and return normalized text. | Must enforce MIME whitelist, size limits, timeouts (≤30s), no external calls. |
| `FeedbackAdapterProtocol` | ```python\nclass FeedbackAdapterProtocol(Protocol):\n    def analyze(self, *, criteria: Sequence[str],\n                submission_text: str) -> FeedbackResult: ...\n``` | Produce deterministic formative feedback (scores, markdown message). | Uses local Ollama text model; no network access; logs only model/runtime metadata. |
| `LearningSubmissionEventPort` (optional) | ```python\nclass LearningSubmissionEventPort(Protocol):\n    def emit_ocr_requested(self, payload: OCRRequestedEvent) -> None: ...\n    def emit_analysis_completed(self, payload: AnalysisCompletedEvent) -> None: ...\n``` | Publish domain events for downstream analytics dashboards. | Events carry IDs/metadata but never raw student content. |

Stub implementations exist for tests (`StubOcrAdapter`, `StubFeedbackAdapter`, in-memory queue). Production adapters wrap Ollama/DSPy with resource guards.

---

## 4. Worker Lifecycle & Status Mapping

### Job Table
- `public.learning_submission_ocr_jobs` columns:
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
- Job table `learning_submission_ocr_jobs` with indexes on `visible_at`.
- Worker updates execute via `SECURITY DEFINER` function `learning_queue_consume_job(submission_id uuid, ...)` to keep RLS intact.

Refer to the latest migration plan in `docs/plan/2025-11-01-ki-integration.md` for SQL sketches.

---

## 6. Security & Privacy
- OCR/feedback adapters run on the same network/host (localhost or Unix socket). No outbound network calls.
- Credentials (Ollama tokens, service accounts) live in the secret store (`.env.production` or container secrets).
- Logs contain identifiers (submission UUID, course/task IDs) but never raw text or images.
- Audit log entry per job (`queued`, `processing`, `completed`, `failed`) with actor `ai_worker`.
- CSRF, RLS, and idempotency enforced at HTTP layer; worker path only handles server-to-server traffic.

---

## 7. Observability & Operations
- **Metrics**
  - `analysis_jobs_inflight` (gauge)
  - `ai_worker_processed_total{status}` (counter)
  - `ai_worker_retry_total{phase}` (counter)
  - `ai_worker_failed_total{error_code}` (counter)
  - `ai_worker_duration_seconds` (histogram per step, follow-up)
- **Logs**
  - Strukturierte Warn-/Error-Logs bei Retries/Failures (`submission_id`, `job_id`, `next_visible_at`, `error_code`).
  - Keine Rohinhalte in Logs; nur IDs und gekürzte Fehlermeldungen.
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
- For integration: spin up local Supabase + Ollama in docker compose; avoid live calls in CI (use stubs).
- Red-Green-Refactor disciplined: write failing test, implement minimal code, refactor adapters/ports.

---

## 9. Configuration & Deployment
- Environment variables:
  - `AI_BACKEND=stub|local`
  - `LOCAL_OLLAMA_URL` (e.g. `http://127.0.0.1:11434`)
  - `WORKER_MAX_RETRIES=3`, `WORKER_BACKOFF_SECONDS=10`, `WORKER_LEASE_SECONDS=45`, `WORKER_POLL_INTERVAL=0.5`
- Praxisregel: Nur `AI_BACKEND=local` (plus `AI_FEEDBACK_MODEL` / `OLLAMA_BASE_URL`)
  schaltet DSPy/Ollama frei. Mit dem Default `stub` liefert der Worker bewusst
  nur Platzhalter für Tests und Demoumgebungen.
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
