-- AI usage accounting: technical token counters per model response.
--
-- Why:
--   Teachers need a course-level cost estimate, but the database must not store
--   prompts, answers or provider raw payloads. The worker records one event per
--   observed provider response; teacher reads stay RLS-protected.

create extension if not exists pgcrypto;

create table if not exists public.ai_usage_events (
  id uuid primary key default gen_random_uuid(),
  event_key uuid not null,
  occurred_at timestamptz not null default now(),
  submission_id uuid not null references public.learning_submissions(id) on delete cascade,
  course_id uuid not null references public.courses(id) on delete cascade,
  unit_id uuid not null references public.units(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  student_sub text not null,
  model text not null check (length(btrim(model)) > 0),
  stage text not null,
  modality text not null,
  call_kind text not null,
  usage_known boolean not null,
  input_tokens integer null,
  output_tokens integer null,
  total_tokens integer null,
  unknown_reason text null,
  created_at timestamptz not null default now(),
  constraint ai_usage_events_event_key_unique unique (event_key),
  constraint ai_usage_events_stage_check check (stage in ('ocr', 'analysis', 'feedback')),
  constraint ai_usage_events_modality_check check (modality in ('text', 'visual')),
  constraint ai_usage_events_call_kind_check check (call_kind in ('primary', 'repair', 'no_criteria')),
  constraint ai_usage_events_token_non_negative check (
    (input_tokens is null or input_tokens >= 0)
    and (output_tokens is null or output_tokens >= 0)
    and (total_tokens is null or total_tokens >= 0)
  ),
  constraint ai_usage_events_usage_known_shape check (
    (
      usage_known
      and unknown_reason is null
      and (input_tokens is not null or output_tokens is not null or total_tokens is not null)
    )
    or (
      not usage_known
      and input_tokens is null
      and output_tokens is null
      and total_tokens is null
      and unknown_reason is not null
      and unknown_reason in ('missing_provider_usage')
    )
  )
);

create index if not exists idx_ai_usage_events_course_occurred
  on public.ai_usage_events(course_id, occurred_at desc);

create index if not exists idx_ai_usage_events_course_student_occurred
  on public.ai_usage_events(course_id, student_sub, occurred_at desc);

create index if not exists idx_ai_usage_events_submission
  on public.ai_usage_events(submission_id);

alter table public.ai_usage_events enable row level security;

grant select on public.ai_usage_events to gustav_limited;

drop policy if exists ai_usage_events_select_course_owner on public.ai_usage_events;
create policy ai_usage_events_select_course_owner on public.ai_usage_events
  for select to gustav_limited
  using (
    exists (
      select 1
        from public.courses c
       where c.id = ai_usage_events.course_id
         and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create or replace function public.learning_worker_record_ai_usage(
  p_submission_id uuid,
  p_event_key uuid,
  p_model text,
  p_stage text,
  p_modality text,
  p_call_kind text,
  p_usage_known boolean,
  p_input_tokens integer,
  p_output_tokens integer,
  p_total_tokens integer,
  p_unknown_reason text
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_submission record;
begin
  if p_submission_id is null or p_event_key is null then
    raise exception 'learning_worker_record_ai_usage: missing required identifier';
  end if;

  select ls.course_id,
         ls.task_id,
         ls.student_sub,
         t.unit_id
    into v_submission
    from public.learning_submissions ls
    join public.unit_tasks t on t.id = ls.task_id
   where ls.id = p_submission_id;

  if not found then
    raise exception 'learning_worker_record_ai_usage: submission not found';
  end if;

  insert into public.ai_usage_events (
    event_key,
    submission_id,
    course_id,
    unit_id,
    task_id,
    student_sub,
    model,
    stage,
    modality,
    call_kind,
    usage_known,
    input_tokens,
    output_tokens,
    total_tokens,
    unknown_reason
  )
  values (
    p_event_key,
    p_submission_id,
    v_submission.course_id,
    v_submission.unit_id,
    v_submission.task_id,
    v_submission.student_sub,
    btrim(p_model),
    p_stage,
    p_modality,
    p_call_kind,
    p_usage_known,
    p_input_tokens,
    p_output_tokens,
    p_total_tokens,
    p_unknown_reason
  )
  on conflict (event_key) do nothing;
end;
$$;

revoke all on function public.learning_worker_record_ai_usage(
  uuid, uuid, text, text, text, text, boolean, integer, integer, integer, text
) from public;

grant execute on function public.learning_worker_record_ai_usage(
  uuid, uuid, text, text, text, text, boolean, integer, integer, integer, text
) to gustav_worker;
