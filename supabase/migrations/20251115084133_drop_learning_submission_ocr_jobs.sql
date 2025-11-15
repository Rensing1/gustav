-- Migration: Remove the retired legacy learning submission OCR queue.

set search_path = public, pg_temp;

do $$ begin
  if to_regclass('public.learning_submission_ocr_jobs') is not null then
    execute 'drop table if exists public.learning_submission_ocr_jobs cascade';
  end if;
exception when others then
  raise notice 'Failed to drop legacy table learning_submission_ocr_jobs: %', sqlerrm;
  raise;
end $$;

-- Defensive cleanup in case the index survived previous renames.
drop index if exists public.learning_submission_ocr_jobs_visible_idx;
