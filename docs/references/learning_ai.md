# Learning AI — Reference

Purpose: Explain how GUSTAV processes learning submissions with AI (OCR + formative feedback) while keeping the Learning bounded context consistent with Clean Architecture, KISS, and security-first principles.

This document complements `docs/references/learning.md`. It focuses on the AI-specific adapters, worker lifecycle, observability, configuration, and operational requirements.

---

## 1. Purpose & Scope
- **OCR**: Extract handwritten or printed text from image/PDF submissions and populate `text_body`.
- **Feedback**: Generate formative feedback (and optional rubric scoring) from `text_body` using DSPy programs.
- **Endpoint**: Inference runs against an operator-configured **OpenAI-compatible API endpoint** (`OPENAI_BASE_URL`).
  - The endpoint may be local or remote; GUSTAV does not enforce host/path rules.
  - Privacy/GDPR responsibility is therefore shared: operators must ensure the endpoint is compliant for student data.
- **Async-first**: Submissions with `kind=image|file` return `202` with `analysis_status=pending`. A worker processes OCR + feedback and updates the submission to `completed` or `failed`.
- **Teacher-only context**: Tasks can include `teacher_context_md` (KI-Kontext/Wissensbasis). It is used as model context but must never be exposed in student-facing DTOs.

---

## 2. Architecture Overview
1. **HTTP Layer** validates request & permissions, calls the use case `IngestLearningSubmission`.
2. **Use Case** stores the submission with `analysis_status=pending` (for text/image/file) and enqueues a job via the queue port.
3. **Worker** (`process_learning_submission_jobs`) leases jobs FIFO, runs OCR (if needed), runs feedback analysis, persists results, and emits follow-up events.
4. **Persistence** is guarded by repository functions and RLS. Worker updates go through `SECURITY DEFINER` helpers to mutate `analysis_status`, `analysis_json`, `feedback_md`.
5. **Observability**: Structured logs + counters/gauges.

---

## 3. Ports & Adapter Contracts

| Port / Adapter | Signature (Python typing) | Responsibility | Security Notes |
| --- | --- | --- | --- |
| `SubmissionStoragePort` | ```python\nclass SubmissionStoragePort(Protocol):\n    def create_presign(self, *, course_id: UUID, task_id: UUID, student_sub: str,\n                       mime_type: str, size_bytes: int) -> PresignResult: ...\n    def verify_object(self, *, storage_key: str, sha256: str,\n                      size_bytes: int) -> StorageVerifyResult: ...\n    def stream_to_local_tmp(self, *, storage_key: str) -> Iterator[bytes]: ...\n``` | Presigned uploads, verification, optional streaming for local OCR. | Uses service credentials; enforces namespacing `submissions/{course}/{task}/{student}/...`. |
| `LearningSubmissionQueuePort` | ```python\nclass LearningSubmissionQueuePort(Protocol):\n    def enqueue(self, job: SubmissionJobPayload) -> None: ...\n    def lease_next(self, *, now: datetime) -> Optional[QueuedJob]: ...\n    def ack(self, job_id: UUID) -> None: ...\n    def retry_later(self, job_id: UUID, *, visible_at: datetime) -> None: ...\n``` | Queue backed by `public.learning_submission_jobs`. | Only worker role can lease/ack jobs. |
| `VisionAdapterProtocol` | ```python\nclass VisionAdapterProtocol(Protocol):\n    def extract(self, *, submission: dict, job_payload: dict) -> VisionResult: ...\n``` | OCR via DSPy (`VisionOcrSignature` → `VisionResult.text_md`). | Must enforce MIME whitelist, size limits, and never log extracted text. |
| `FeedbackAdapterProtocol` | ```python\nclass FeedbackAdapterProtocol(Protocol):\n    def analyze(self, *, text_md: str, criteria: Sequence[str]) -> FeedbackResult: ...\n``` | DSPy-only feedback for text submissions. | Must not log student text or teacher context; validates required feedback headings. |

Production adapters:
- OCR: `backend/learning/adapters/local_vision.py` (DSPy-only, OpenAI-compatible endpoint).
- Feedback: `backend/learning/adapters/local_feedback.py` (DSPy-only, OpenAI-compatible endpoint; visual tasks via `analyze_visual`).
  - Note: Concrete adapters may accept additional optional kwargs (`instruction_md`, `teacher_context_md`). The worker passes them when supported.

---

## 4. Worker Lifecycle & Status Mapping

### Job Table
- `public.learning_submission_jobs` columns:
  - `status`: `queued` → `leased` → (`failed` | delete on success)
  - `retry_count`, `visible_at`: exponential backoff
  - `payload`: JSON with `submission_id`, `storage_key`, `mime_type`, `sha256`, `student_sub`, …

### Processing Flow (High-level)
1. Lease jobs via `FOR UPDATE SKIP LOCKED` and commit immediately (short transaction).
2. Fetch submission + task context, commit (short transaction).
3. Run external I/O (DSPy calls) **outside** any DB transaction.
4. Persist results/retries/failures via helper functions (short transaction per write).

Why this matters:
- Avoids the “idle in transaction” worker stall pattern when an external LLM/VLM call hangs.

---

## 5. Configuration & Deployment

### 5.1 Environment variables (overview)

| Name | Required | Scope | Notes |
| --- | --- | --- | --- |
| `OPENAI_BASE_URL` | yes | Worker | OpenAI-compatible base URL as-is (may include path like `/api/v1`). |
| `OPENAI_API_KEY` | no | Worker | Optional token; defaults to a no-op value when empty. |
| `AI_TEXT_MODEL` | yes | Feedback | One model for text analysis + synthesis. |
| `AI_OCR_MODEL` | yes | OCR | Vision model used for OCR/text extraction. |
| `AI_VISUAL_MODEL` | yes (for visual tasks) | Visual | Required for task kind `visual` (no fallback). |
| `AI_TEXT_TEMPERATURE` | no | Feedback | Default `0.0`. |
| `AI_OCR_TEMPERATURE` | no | OCR | Default `0.0`. |
| `AI_VISUAL_TEMPERATURE` | no | Visual | Default `0.0`. |
| `AI_TEXT_THINK_LEVEL` | no | Feedback | GPT-OSS only: `low|medium|high` (defaults to `low` when unset). Ignored for non-GPT-OSS models. |
| `AI_OCR_THINK_LEVEL` | no | OCR | GPT-OSS only: `low|medium|high` (defaults to `low` when unset). Ignored for non-GPT-OSS models. |
| `AI_VISUAL_THINK_LEVEL` | no | Visual | GPT-OSS only: `low|medium|high` (defaults to `low` when unset). Ignored for non-GPT-OSS models. |
| `LEARNING_VISION_ADAPTER` | no | Worker DI | Override module path (default `backend.learning.adapters.local_vision`). |
| `LEARNING_FEEDBACK_ADAPTER` | no | Worker DI | Override module path (default `backend.learning.adapters.local_feedback`). |
| `DSPY_CACHEDIR` | no | Worker container | Disk cache directory (compose default: `/tmp/dspy_cache`; override via `.env`). |
| `DSPY_CACHE_LIMIT` | no | Worker container | Disk cache size limit in bytes (compose default: `4294967296`; override via `.env`). |
| `WORKER_CONCURRENCY` | no | Worker | Parallelism (default `1`, hard cap in code). |
| `WORKER_MAX_RETRIES` | no | Worker | Default `3`. |
| `WORKER_BACKOFF_SECONDS` | no | Worker | Base backoff, default `10`. |
| `WORKER_LEASE_SECONDS` | no | Worker | Default `45` (effective lease window is multiplied internally). |
| `WORKER_POLL_INTERVAL` | no | Worker | Default `0.5`. |

Additional storage-related env (security-critical for OCR fetch paths):
- `SUPABASE_URL`, `SUPABASE_PUBLIC_URL`: define trusted hosts for remote fetch of uploaded files.
- `SUPABASE_SERVICE_ROLE_KEY`: used only for server-side storage fetches; never sent to untrusted hosts.
- `STORAGE_VERIFY_ROOT`: local path for verifying and reading uploads in Docker/dev; used for PDF page stitching.

---

## References
- Plan: `docs/plan/2026-01-10-learning-feedback-dspy-only-no-fallback.md`
- Prompts/Signatures: `docs/references/LLM-Prompts.md`
