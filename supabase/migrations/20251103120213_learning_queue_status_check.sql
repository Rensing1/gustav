-- Migration: Align queue status constraint with leased workflow.

set search_path = public, pg_temp;

do $$ begin
  if exists (
      select 1
        from information_schema.table_constraints
       where table_schema = 'public'
         and table_name = 'learning_submission_jobs'
         and constraint_name = 'learning_submission_ocr_jobs_status_check'
  ) then
    alter table public.learning_submission_jobs
      drop constraint learning_submission_ocr_jobs_status_check;
  end if;
exception when undefined_object then
  null;
end $$;

alter table if exists public.learning_submission_jobs
  drop constraint if exists learning_submission_jobs_status_check;

alter table if exists public.learning_submission_jobs
  add constraint learning_submission_jobs_status_check
    check (status in ('queued','leased','failed'));

