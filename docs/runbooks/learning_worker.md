# Learning Worker — Runbook

Purpose: Operate and troubleshoot the asynchronous learning worker (vision + feedback).

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

## Retries & Failures
- Transient adapter errors → `_nack_retry` with exponential backoff; submission stays `pending` and `error_code` is `vision_retrying|feedback_retrying`.
- Permanent errors → submission `failed` via `public.learning_worker_update_failed(...)` and job `status=failed`.
- Completed → `public.learning_worker_update_completed(...)` sets `text_body`, `feedback_md`, and `analysis_json (criteria.v1)`.

## Observability
- Gauges/Counters: `analysis_jobs_inflight`, `ai_worker_retry_total{phase}`, `ai_worker_failed_total{error_code}`.
- Logs should not contain PII; error messages are truncated to 1024 chars.

## Common Issues
- 503 on health probe with `db_role failed`: ensure role `gustav_worker` exists (or worker DSN points to app login) and function grants include `gustav_limited`.
- Jobs not picked up: confirm `(status='queued' and visible_at <= now())` and no long-lived leases.
- RLS blocks submission updates: ensure helpers are installed and `gustav_worker` has EXECUTE on them.

## Commands
- Start: `docker compose up -d --build` (worker auto-starts).
- Migrations: `supabase migration up`.
- Tests: `.venv/bin/pytest -q`.
