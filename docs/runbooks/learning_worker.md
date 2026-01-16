# Learning Worker — Runbook

Purpose: Operate and troubleshoot the asynchronous learning worker (OCR + feedback).

## Credentials & DSN
- Production: create a dedicated DB role `gustav_worker` without committing passwords to VCS.
  - SQL (run in admin context): `create role gustav_worker login; alter role gustav_worker inherit;` then `grant gustav_limited to gustav_worker;`
  - Set the password out-of-band via secret store; never in migrations.
  - Configure the worker with `LEARNING_DATABASE_URL=postgresql://gustav_worker:<SECRET>@<host>:<port>/postgres`.
- Development: default to the application login DSN (IN ROLE `gustav_limited`) via environment.
- Web/API uses `DATABASE_URL` (app login). Avoid service-role DSNs except for session store internals.

## Health Probe
- Endpoint: `GET /internal/health/learning-worker` (teacher/operator only).
- Response: `200 { status: "healthy", currentRole, checks: [...] }` or `503` when degraded.
- Cache headers: `Cache-Control: private, no-store`, `Vary: Origin`.
- DB function: `public.learning_worker_health_probe()` (SECURITY DEFINER) checks role presence and queue visibility.

## Queue & Leasing
- Table: `public.learning_submission_jobs`.
- Status: `queued|leased|failed`; leased rows include `lease_key` and `leased_until`.
- Index: `(status, visible_at)`; worker uses `FOR UPDATE SKIP LOCKED` to lease.

## DSPy Pipelines (Current)
- Text feedback: `backend/learning/adapters/dspy/feedback_program.analyze_feedback(...)`
- Visual feedback (task kind `visual`): `backend/learning/adapters/dspy/visual_feedback_program.analyze_visual_feedback(...)`
- OCR/text extraction: `backend/learning/adapters/dspy/vision_program.extract_text_from_image(...)`
- LM configuration happens per adapter call via `dspy.context(...)` (thread-local, no global `dspy.configure()`); history is disabled (`disable_history=True`).
- Fail-fast: no deterministic fallback outputs. Empty/invalid model output triggers worker retry (and may fail after max retries).

## Retries & Failures
- Transient adapter errors → `_nack_retry` with exponential backoff; submission stays `pending` and `error_code` is `vision_retrying|feedback_retrying`.
- Permanent errors → submission `failed` via `public.learning_worker_update_failed(...)` and job `status=failed`.
- Completed → `public.learning_worker_update_completed(...)` sets `text_body`, `feedback_md`, and `analysis_json` (usually schema `criteria.v2`; for tasks without criteria `analysis_json` is `{}`).

## Observability
- Gauges/Counters: `analysis_jobs_inflight`, `ai_worker_retry_total{phase}`, `ai_worker_failed_total{error_code}`.
- Logs should not contain PII; error messages are truncated to 1024 chars.
- Useful log markers:
  - `learning.adapters.selected ...`
  - `Vision retry scheduled ... reason=...`
  - `Feedback retry scheduled ... reason=...`

## Common Issues
- Retries due to missing AI config:
  - `missing_OPENAI_BASE_URL`, `missing_AI_TEXT_MODEL`, `missing_AI_OCR_MODEL`
  - Fix: set env vars in `.env` and recreate the container (`docker compose up -d --build --force-recreate learning-worker`).
- Visual tasks fail immediately:
  - Reason: `missing_AI_VISUAL_MODEL` (visual tasks are fail-fast; no fallback).
- OCR output too long:
  - Reason: `ocr_text_too_long` (transient; can succeed with a different model/backend).
- Queue backlog / jobs not picked up:
  - Confirm `(status='queued' and visible_at <= now())` and no long-lived leases.
  - Increase throughput carefully via `WORKER_CONCURRENCY` (default `1`, hard cap in code).
- DB "idle in transaction":
  - Should not happen; the worker commits before external LLM/VLM calls. If you still observe it, verify you are running the updated worker image.

## Commands
- Start: `docker compose up -d --build` (worker auto-starts).
- Migrations: `supabase migration up`.
- Tests: `.venv/bin/pytest -q`.

## Preflight Checklist (Local = Prod)
1) Container starten/neu erstellen
- `docker compose up -d --build`

2) Runtime‑ENV im Worker prüfen
- `docker compose exec -T learning-worker sh -lc 'printf "OPENAI_BASE_URL=%s\nAI_TEXT_MODEL=%s\nAI_OCR_MODEL=%s\nAI_VISUAL_MODEL=%s\nAI_TEXT_TEMPERATURE=%s\nAI_OCR_TEMPERATURE=%s\nAI_VISUAL_TEMPERATURE=%s\nDSPY_CACHEDIR=%s\nDSPY_CACHE_LIMIT=%s\nWORKER_CONCURRENCY=%s\n" "$OPENAI_BASE_URL" "$AI_TEXT_MODEL" "$AI_OCR_MODEL" "$AI_VISUAL_MODEL" "$AI_TEXT_TEMPERATURE" "$AI_OCR_TEMPERATURE" "$AI_VISUAL_TEMPERATURE" "$DSPY_CACHEDIR" "$DSPY_CACHE_LIMIT" "$WORKER_CONCURRENCY"'`

3) Worker‑Logs auf Retry/Fehler prüfen
- `docker compose logs -n 200 learning-worker | rg "learning.adapters.selected|retry scheduled|_failed|completed"`

4) DB‑Persistenz (eine Test‑Einreichung vorausgesetzt)
- `psql 'postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres' -c "select analysis_status, left(feedback_md,120) as feedback, analysis_json->>'schema' as schema, created_at from public.learning_submissions order by created_at desc limit 5;"`

## DSPy Cache
- Configured in `docker-compose.yml` for `learning-worker` only:
  - `DSPY_CACHEDIR=/tmp/dspy_cache`
  - `DSPY_CACHE_LIMIT=34359738368` (32 GiB)
- Stored inside the container filesystem (cleared on container restart by design).
