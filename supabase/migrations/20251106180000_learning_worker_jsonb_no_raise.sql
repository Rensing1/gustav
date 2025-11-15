-- Make JSONB overload of learning_worker_update_completed tolerant (no RAISE)
-- Mirrors the JSON overload semantics to reduce test flakiness and races.
set search_path = public, pg_temp;

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
       and analysis_status in ('pending', 'extracted');
    -- No RAISE on mismatch: tolerate already-completed/failed states.
end;
$$;

grant execute on function public.learning_worker_update_completed(uuid, text, text, jsonb) to gustav_worker;

