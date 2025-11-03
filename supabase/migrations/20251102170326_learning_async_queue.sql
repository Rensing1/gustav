-- Generated via `supabase migration new learning_async_queue`
-- Purpose: Enable async processing for learning submissions
-- - Adjust constraints for image/file kinds (text_body optional)
-- - Add pending/completed/failed analysis_status constraint
-- - Add OCR retry metadata
-- - Create lightweight job queue table for worker

set search_path = public, pg_temp;

-- 1) Constraints for image kind: require metadata, allow empty text_body
alter table if exists public.learning_submissions drop constraint if exists learning_submissions_image_kind;
alter table if exists public.learning_submissions add constraint learning_submissions_image_kind
  check (
    kind <> 'image' or (
      storage_key is not null and
      mime_type in ('image/jpeg','image/png') and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

-- 1b) Constraints for file kind (PDF only), allow empty text_body until OCR
alter table if exists public.learning_submissions drop constraint if exists learning_submissions_file_kind;
alter table if exists public.learning_submissions add constraint learning_submissions_file_kind
  check (
    kind <> 'file' or (
      storage_key is not null and
      mime_type = 'application/pdf' and
      size_bytes between 1 and 10485760 and
      sha256 ~ '^[0-9a-f]{64}$'
    )
  );

-- 2) Restrict analysis_status to pending/completed/failed
alter table if exists public.learning_submissions drop constraint if exists learning_submissions_analysis_status_check;
alter table if exists public.learning_submissions add constraint learning_submissions_analysis_status_check
  check (analysis_status in ('pending','completed','failed'));

-- 3) OCR retry metadata for worker observability
do $$ begin
  alter table public.learning_submissions
    add column if not exists ocr_attempts integer not null default 0,
    add column if not exists ocr_last_error text,
    add column if not exists ocr_last_attempt_at timestamptz;
exception when undefined_table then
  -- table may not exist yet in some environments; skip
  null;
end $$;

-- 4) Job queue for async OCR/analysis worker
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

-- 5) Minimal privileges for application role (RLS remains off for this queue)
do $$ begin
  perform 1 from pg_roles where rolname = 'gustav_limited';
  if found then
    grant insert, select, update, delete on table public.learning_submission_ocr_jobs to gustav_limited;
  end if;
exception when others then
  -- Best-effort grants; environments without role will skip
  null;
end $$;
