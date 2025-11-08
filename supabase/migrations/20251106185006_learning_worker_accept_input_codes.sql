-- Allow worker helper functions to persist preprocessing input error codes.
set search_path = public, pg_temp;

-- Align error_code column with new enumeration (matches OpenAPI contract).
alter table if exists public.learning_submissions
  drop constraint if exists learning_submissions_error_code_check;

alter table if exists public.learning_submissions
  add constraint learning_submissions_error_code_check
  check (
    error_code is null
    or error_code in (
      'vision_retrying',
      'vision_failed',
      'feedback_retrying',
      'feedback_failed',
      'input_corrupt',
      'input_unsupported',
      'input_too_large'
    )
  );

-- Accept input_* codes while keeping vision/feedback semantics intact.
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
    if p_error_code not in (
        'vision_failed',
        'feedback_failed',
        'input_corrupt',
        'input_unsupported',
        'input_too_large'
    ) then
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
               when p_error_code in ('vision_failed', 'input_corrupt', 'input_unsupported', 'input_too_large') then trimmed
               else vision_last_error
           end,
           vision_last_attempt_at = case
               when p_error_code in ('vision_failed', 'input_corrupt', 'input_unsupported', 'input_too_large') then now()
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
       and analysis_status in ('pending', 'extracted');
    -- No RAISE on mismatch: tolerate already-completed/failed states.
end;
$$;

grant execute on function public.learning_worker_update_failed(uuid, text, text) to gustav_worker;
