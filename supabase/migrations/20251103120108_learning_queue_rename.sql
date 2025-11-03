-- Migration: Align learning submission queue with vision/feedback worker naming.
-- - Rename legacy OCR columns to vision_*
-- - Create (or migrate) queue table `learning_submission_jobs`
--   with leasing metadata compatible with the new worker.

set search_path = public, pg_temp;

-- 1) Rename OCR tracking columns when present.
do $$ begin
  if exists (
      select 1
        from information_schema.columns
       where table_schema = 'public'
         and table_name = 'learning_submissions'
         and column_name = 'ocr_attempts'
  ) then
    alter table public.learning_submissions
      rename column ocr_attempts to vision_attempts;
  end if;
exception when undefined_column then
  null;
end $$;

do $$ begin
  if exists (
      select 1
        from information_schema.columns
       where table_schema = 'public'
         and table_name = 'learning_submissions'
         and column_name = 'ocr_last_error'
  ) then
    alter table public.learning_submissions
      rename column ocr_last_error to vision_last_error;
  end if;
exception when undefined_column then
  null;
end $$;

do $$ begin
  if exists (
      select 1
        from information_schema.columns
       where table_schema = 'public'
         and table_name = 'learning_submissions'
         and column_name = 'ocr_last_attempt_at'
  ) then
    alter table public.learning_submissions
      rename column ocr_last_attempt_at to vision_last_attempt_at;
  end if;
exception when undefined_column then
  null;
end $$;

-- Ensure defaults exist after rename (no-op if already set).
alter table if exists public.learning_submissions
  alter column vision_attempts set default 0;

-- 2) Queue table: migrate legacy table or create fresh.
do $$ begin
  if to_regclass('public.learning_submission_jobs') is null
     and to_regclass('public.learning_submission_ocr_jobs') is not null then
    -- Rename legacy table to the new name before altering structure.
    execute 'alter table public.learning_submission_ocr_jobs rename to learning_submission_jobs';
    -- Legacy index rename
    if to_regclass('public.learning_submission_ocr_jobs_visible_idx') is not null then
      execute 'alter index public.learning_submission_ocr_jobs_visible_idx rename to learning_submission_jobs_visible_idx';
    end if;
  end if;
end $$;

-- Create table with leasing columns when missing.
create table if not exists public.learning_submission_jobs (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.learning_submissions(id) on delete cascade,
  payload jsonb not null,
  status text not null default 'queued' check (status in ('queued','leased','failed')),
  retry_count integer not null default 0,
  visible_at timestamptz not null default now(),
  lease_key uuid,
  leased_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Ensure leasing columns exist when table was renamed instead of created.
alter table public.learning_submission_jobs
  add column if not exists lease_key uuid,
  add column if not exists leased_until timestamptz;

-- Index: ensure it matches new status semantics.
drop index if exists public.learning_submission_jobs_visible_idx;
create index if not exists learning_submission_jobs_visible_idx
  on public.learning_submission_jobs (status, visible_at);

-- Grant queue access to application role.
do $$ begin
  perform 1 from pg_roles where rolname = 'gustav_limited';
  if found then
    grant insert, select, update, delete on table public.learning_submission_jobs to gustav_limited;
  end if;
exception when others then
  null;
end $$;
