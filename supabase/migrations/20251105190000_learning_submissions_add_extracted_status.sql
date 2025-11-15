-- Learning submissions: allow intermediate 'extracted' analysis status
set search_path = public, pg_temp;

-- Relax analysis_status constraint to include 'extracted' between pending and completed
alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_analysis_status_check;

alter table if exists public.learning_submissions
  add constraint learning_submissions_analysis_status_check
  check (analysis_status in ('pending','extracted','completed','failed'));

