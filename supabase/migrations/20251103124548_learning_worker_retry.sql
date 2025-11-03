-- Migration: learning worker retry/backoff + security-definer helpers
-- Purpose:
--   * add queue/job metadata to support retries with exponential backoff
--   * extend submissions table with feedback retry bookkeeping
--   * provide SECURITY DEFINER helpers used by the worker tests

set search_path = public, pg_temp;

-- Queue column needed for storing per-job error codes (optional for auditing).
alter table if exists public.learning_submission_jobs
  add column if not exists error_code text;

-- Feedback retry bookkeeping mirrors the existing vision columns.
alter table if exists public.learning_submissions
  add column if not exists feedback_last_attempt_at timestamptz,
  add column if not exists feedback_last_error text;

-- Helper: mark submission as completed after successful Vision + Feedback.
create or replace function public.learning_worker_update_completed(
    p_submission_id uuid,
    p_text_body text,
    p_feedback_md text,
    p_analysis_json jsonb
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    update public.learning_submissions
       set analysis_status = 'completed',
           text_body = p_text_body,
           feedback_md = p_feedback_md,
           analysis_json = p_analysis_json,
           error_code = null,
           completed_at = now(),
           vision_attempts = coalesce(vision_attempts, 0) + 1,
           vision_last_error = null,
           vision_last_attempt_at = now(),
           feedback_last_attempt_at = now(),
           feedback_last_error = null
     where id = p_submission_id
       and analysis_status = 'pending';

    if not found then
        raise exception 'learning_worker_update_completed: submission must be pending';
    end if;
end;
$$;

comment on function public.learning_worker_update_completed(uuid, text, text, jsonb)
  is 'Worker helper: transition pending submission to completed state while clearing retry metadata.';

-- Helper: mark submission as failed with strict error-code validation.
create or replace function public.learning_worker_update_failed(
    p_submission_id uuid,
    p_error_code text,
    p_last_error text
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    trimmed text := left(coalesce(p_last_error, ''), 1024);
begin
    if p_error_code not in ('vision_failed', 'feedback_failed') then
        raise exception 'learning_worker_update_failed: invalid error code %', p_error_code;
    end if;

    update public.learning_submissions
       set analysis_status = 'failed',
           error_code = p_error_code,
           vision_attempts = case
               when p_error_code = 'vision_failed' then coalesce(vision_attempts, 0) + 1
               else vision_attempts
           end,
           vision_last_error = case
               when p_error_code = 'vision_failed' then trimmed
               else vision_last_error
           end,
           vision_last_attempt_at = case
               when p_error_code = 'vision_failed' then now()
               else vision_last_attempt_at
           end,
           feedback_last_error = case
               when p_error_code = 'feedback_failed' then trimmed
               else feedback_last_error
           end,
           feedback_last_attempt_at = case
               when p_error_code = 'feedback_failed' then now()
               else feedback_last_attempt_at
           end
     where id = p_submission_id
       and analysis_status = 'pending';

    if not found then
        raise exception 'learning_worker_update_failed: submission must be pending';
    end if;
end;
$$;

comment on function public.learning_worker_update_failed(uuid, text, text)
  is 'Worker helper: transition pending submission to failed with sanitized error details.';

-- Helper: record retry bookkeeping without granting broad UPDATE access to the worker.
create or replace function public.learning_worker_mark_retry(
    p_submission_id uuid,
    p_phase text,
    p_message text,
    p_attempted_at timestamptz
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    trimmed text := left(coalesce(p_message, ''), 1024);
begin
    if p_phase = 'vision' then
        update public.learning_submissions
           set vision_attempts = coalesce(vision_attempts, 0) + 1,
               vision_last_attempt_at = p_attempted_at,
               vision_last_error = trimmed,
               error_code = 'vision_retrying'
         where id = p_submission_id
           and analysis_status = 'pending';
    elsif p_phase = 'feedback' then
        update public.learning_submissions
           set feedback_last_attempt_at = p_attempted_at,
               feedback_last_error = trimmed,
               error_code = 'feedback_retrying'
         where id = p_submission_id
           and analysis_status = 'pending';
    else
        raise exception 'learning_worker_mark_retry: invalid phase %', p_phase;
    end if;

    if not found then
        raise exception 'learning_worker_mark_retry: submission not pending';
    end if;
end;
$$;

comment on function public.learning_worker_mark_retry(uuid, text, text, timestamptz)
  is 'Worker helper: update retry metadata for vision/feedback while keeping submission pending.';

grant execute on function public.learning_worker_update_completed(uuid, text, text, jsonb) to gustav_worker;
grant execute on function public.learning_worker_update_failed(uuid, text, text) to gustav_worker;
grant execute on function public.learning_worker_mark_retry(uuid, text, text, timestamptz) to gustav_worker;
