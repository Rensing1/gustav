-- Migration: Ensure learning_submission_jobs has leasing metadata columns.

set search_path = public, pg_temp;

alter table if exists public.learning_submission_jobs
  add column if not exists lease_key uuid,
  add column if not exists leased_until timestamptz;

-- Refresh index to ensure status/visible_at coverage.
drop index if exists public.learning_submission_jobs_visible_idx;
create index if not exists learning_submission_jobs_visible_idx
  on public.learning_submission_jobs (status, visible_at);

