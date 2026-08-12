-- Learning: narrowly scoped worker helpers for deterministic practice completion.

set check_function_bodies = off;
set search_path = public, pg_temp;

create or replace function public.learning_worker_get_practice_attempt_context(
  p_submission_id uuid
)
returns table (
  attempt_id uuid,
  criteria text[],
  presentation_number integer,
  solution_seen boolean,
  support_pending boolean,
  previous_stability_days double precision,
  previous_interval_seconds bigint,
  previous_due_at timestamptz,
  previous_last_attempt_at timestamptz,
  previous_review_count integer,
  previous_scheduler_version text,
  completed_at timestamptz
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  selected_attempt public.learning_practice_attempts%rowtype;
  selected_item public.learning_practice_session_items%rowtype;
  selected_state public.learning_practice_states%rowtype;
begin
  select attempt.*
    into selected_attempt
    from public.learning_practice_attempts attempt
   where attempt.submission_id = p_submission_id
     and attempt.status = 'pending'
   for update;
  if not found then
    return;
  end if;

  select item.*
    into selected_item
    from public.learning_practice_session_items item
   where item.id = selected_attempt.session_item_id
   for update;

  select state.*
    into selected_state
    from public.learning_practice_states state
   where state.course_id = selected_attempt.course_id
     and state.student_sub = selected_attempt.student_sub
     and state.task_id = selected_attempt.task_id
   for update;

  return query
  select selected_attempt.id,
         selected_item.criteria,
         selected_attempt.presentation_number,
         (selected_attempt.solution_seen or selected_item.solution_viewed_at is not null),
         coalesce(selected_state.support_pending, false),
         selected_state.stability_days,
         selected_state.interval_seconds,
         selected_state.due_at,
         selected_state.last_attempt_at,
         selected_state.review_count,
         selected_state.scheduler_version,
         clock_timestamp();
end;
$$;

create or replace function public.learning_worker_complete_practice_attempt(
  p_attempt_id uuid,
  p_fulfillment double precision,
  p_classification text,
  p_supported boolean,
  p_stability_days double precision,
  p_interval_seconds bigint,
  p_due_at timestamptz,
  p_completed_at timestamptz,
  p_feedback_md text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  selected_attempt public.learning_practice_attempts%rowtype;
  previous_state public.learning_practice_states%rowtype;
begin
  if p_classification not in ('secure', 'partial', 'insufficient')
     or p_fulfillment < 0 or p_fulfillment > 1
     or p_stability_days <= 0 or p_interval_seconds <= 0 then
    raise exception 'invalid_practice_completion';
  end if;

  select attempt.*
    into selected_attempt
    from public.learning_practice_attempts attempt
   where attempt.id = p_attempt_id
   for update;
  if not found or selected_attempt.status <> 'pending' then
    return false;
  end if;

  select state.*
    into previous_state
    from public.learning_practice_states state
   where state.course_id = selected_attempt.course_id
     and state.student_sub = selected_attempt.student_sub
     and state.task_id = selected_attempt.task_id
   for update;

  insert into public.learning_practice_states (
    course_id, student_sub, task_id, stability_days, interval_seconds,
    due_at, last_attempt_at, last_fulfillment, last_classification,
    review_count, scheduler_version, support_pending
  ) values (
    selected_attempt.course_id, selected_attempt.student_sub, selected_attempt.task_id,
    p_stability_days, p_interval_seconds, p_due_at, p_completed_at,
    p_fulfillment, p_classification, 1, 'gustav-practice-v1', false
  )
  on conflict (course_id, student_sub, task_id) do update
    set stability_days = excluded.stability_days,
        interval_seconds = excluded.interval_seconds,
        due_at = excluded.due_at,
        last_attempt_at = excluded.last_attempt_at,
        last_fulfillment = excluded.last_fulfillment,
        last_classification = excluded.last_classification,
        review_count = public.learning_practice_states.review_count + 1,
        scheduler_version = excluded.scheduler_version,
        support_pending = case
          when p_supported then false
          else public.learning_practice_states.support_pending
        end;

  update public.learning_practice_attempts
     set solution_seen = selected_attempt.solution_seen or p_supported,
         supported_recall = p_supported,
         original_due_at = previous_state.due_at,
         original_stability_days = previous_state.stability_days,
         original_interval_seconds = previous_state.interval_seconds,
         fulfillment = p_fulfillment,
         classification = p_classification,
         scheduler_version = 'gustav-practice-v1',
         resulting_stability_days = p_stability_days,
         resulting_interval_seconds = p_interval_seconds,
         resulting_due_at = p_due_at,
         feedback_md = p_feedback_md,
         status = 'completed',
         scheduler_applied_at = p_completed_at,
         completed_at = p_completed_at,
         error_code = null
   where id = p_attempt_id
     and status = 'pending';

  update public.learning_practice_session_items
     set status = 'feedback'
   where id = selected_attempt.session_item_id
     and status = 'awaiting_analysis';
  return true;
end;
$$;

create or replace function public.learning_worker_fail_practice_attempt(
  p_submission_id uuid,
  p_error_code text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  selected_attempt public.learning_practice_attempts%rowtype;
begin
  select attempt.*
    into selected_attempt
    from public.learning_practice_attempts attempt
   where attempt.submission_id = p_submission_id
   for update;
  if not found or selected_attempt.status <> 'pending' then
    return false;
  end if;
  update public.learning_practice_attempts
     set status = 'failed', error_code = left(p_error_code, 100), completed_at = now()
   where id = selected_attempt.id and status = 'pending';
  update public.learning_practice_session_items
     set status = 'active'
   where id = selected_attempt.session_item_id and status = 'awaiting_analysis';
  return true;
end;
$$;

revoke all on function public.learning_worker_get_practice_attempt_context(uuid) from public;
revoke all on function public.learning_worker_complete_practice_attempt(uuid, double precision, text, boolean, double precision, bigint, timestamptz, timestamptz, text) from public;
revoke all on function public.learning_worker_fail_practice_attempt(uuid, text) from public;
grant execute on function public.learning_worker_get_practice_attempt_context(uuid) to gustav_worker;
grant execute on function public.learning_worker_complete_practice_attempt(uuid, double precision, text, boolean, double precision, bigint, timestamptz, timestamptz, text) to gustav_worker;
grant execute on function public.learning_worker_fail_practice_attempt(uuid, text) to gustav_worker;

set check_function_bodies = on;
