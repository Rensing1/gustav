-- Learning: persist practice states, immutable session snapshots and attempts.

set check_function_bodies = off;
set search_path = public, pg_temp;

create table public.learning_practice_states (
  course_id uuid not null references public.courses(id) on delete cascade,
  student_sub text not null,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  stability_days double precision not null check (stability_days > 0),
  interval_seconds bigint not null check (interval_seconds > 0),
  due_at timestamptz not null,
  last_attempt_at timestamptz null,
  last_fulfillment double precision null check (last_fulfillment between 0 and 1),
  last_classification text null check (last_classification in ('secure', 'partial', 'insufficient')),
  review_count integer not null default 0 check (review_count >= 0),
  scheduler_version text not null default 'gustav-practice-v1',
  support_pending boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (course_id, student_sub, task_id)
);

create table public.learning_practice_sessions (
  id uuid primary key default gen_random_uuid(),
  student_sub text not null,
  mode text not null check (mode in ('due', 'exam')),
  status text not null default 'active' check (status in ('active', 'ended')),
  started_at timestamptz not null default now(),
  ended_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((status = 'active' and ended_at is null) or (status = 'ended' and ended_at is not null))
);

create unique index learning_practice_sessions_one_active_per_student
  on public.learning_practice_sessions(student_sub)
  where status = 'active';

create table public.learning_practice_session_stacks (
  session_id uuid not null references public.learning_practice_sessions(id) on delete cascade,
  course_id uuid not null references public.courses(id) on delete cascade,
  practice_module_id uuid not null references public.unit_modules(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (session_id, course_id, practice_module_id)
);

create table public.learning_practice_session_items (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.learning_practice_sessions(id) on delete cascade,
  course_id uuid not null,
  practice_module_id uuid not null,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  task_kind text not null check (task_kind in ('native', 'h5p')),
  instruction_md text not null,
  criteria text[] not null default '{}',
  h5p_content_id text null,
  position integer not null check (position > 0 and position <= 1000),
  status text not null default 'queued' check (
    status in ('queued', 'active', 'awaiting_analysis', 'feedback', 'retry_queued', 'skipped', 'completed')
  ),
  presentation_number integer not null default 1 check (presentation_number between 1 and 2),
  solution_viewed_at timestamptz null,
  completion_token_hash bytea null,
  access_skip_reason text null check (access_skip_reason is null or access_skip_reason = 'access_lost'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (session_id, position),
  foreign key (session_id, course_id, practice_module_id)
    references public.learning_practice_session_stacks(session_id, course_id, practice_module_id)
    on delete cascade
);

create unique index learning_practice_session_items_one_current
  on public.learning_practice_session_items(session_id)
  where status in ('active', 'awaiting_analysis', 'feedback');

create table public.learning_practice_attempts (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.learning_practice_sessions(id) on delete cascade,
  session_item_id uuid not null references public.learning_practice_session_items(id) on delete cascade,
  course_id uuid not null references public.courses(id) on delete cascade,
  student_sub text not null,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  submission_id uuid null references public.learning_submissions(id) on delete set null,
  mode text not null check (mode in ('due', 'exam')),
  presentation_number integer not null check (presentation_number between 1 and 2),
  input_method text not null check (input_method in ('typed', 'h5p')),
  idempotency_key_hash bytea null,
  completion_token_hash bytea null,
  solution_seen boolean not null default false,
  supported_recall boolean not null default false,
  original_due_at timestamptz null,
  original_stability_days double precision null,
  original_interval_seconds bigint null,
  fulfillment double precision null check (fulfillment between 0 and 1),
  classification text null check (classification in ('secure', 'partial', 'insufficient')),
  scheduler_version text not null default 'gustav-practice-v1',
  resulting_stability_days double precision null,
  resulting_interval_seconds bigint null,
  resulting_due_at timestamptz null,
  feedback_md text null,
  status text not null default 'pending' check (status in ('pending', 'completed', 'failed')),
  scheduler_applied_at timestamptz null,
  completed_at timestamptz null,
  error_code text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index learning_practice_attempts_submission_unique
  on public.learning_practice_attempts(submission_id)
  where submission_id is not null;
create unique index learning_practice_attempts_idempotency_unique
  on public.learning_practice_attempts(student_sub, idempotency_key_hash)
  where idempotency_key_hash is not null;
create unique index learning_practice_attempts_completion_token_unique
  on public.learning_practice_attempts(completion_token_hash)
  where completion_token_hash is not null;
create unique index learning_practice_attempts_one_completion_per_presentation
  on public.learning_practice_attempts(session_item_id, presentation_number)
  where status = 'completed';

create index learning_practice_states_due
  on public.learning_practice_states(student_sub, course_id, due_at);
create index learning_practice_items_session_status
  on public.learning_practice_session_items(session_id, status, position);

alter table public.learning_practice_states enable row level security;
alter table public.learning_practice_sessions enable row level security;
alter table public.learning_practice_session_stacks enable row level security;
alter table public.learning_practice_session_items enable row level security;
alter table public.learning_practice_attempts enable row level security;

create trigger trg_learning_practice_states_updated_at
before update on public.learning_practice_states
for each row execute function public.set_updated_at();
create trigger trg_learning_practice_sessions_updated_at
before update on public.learning_practice_sessions
for each row execute function public.set_updated_at();
create trigger trg_learning_practice_items_updated_at
before update on public.learning_practice_session_items
for each row execute function public.set_updated_at();
create trigger trg_learning_practice_attempts_updated_at
before update on public.learning_practice_attempts
for each row execute function public.set_updated_at();

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'learning_practice_states',
    'learning_practice_sessions',
    'learning_practice_session_stacks',
    'learning_practice_session_items',
    'learning_practice_attempts'
  ] loop
    execute format('revoke all on table public.%I from public', table_name);
    execute format('grant select, insert, update on table public.%I to gustav_limited', table_name);
  end loop;
end;
$$;

create policy learning_practice_states_own on public.learning_practice_states
  for all to gustav_limited
  using (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and exists (
      select 1 from public.course_memberships membership
       where membership.course_id = learning_practice_states.course_id
         and membership.student_id = learning_practice_states.student_sub
    )
  )
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and exists (
      select 1 from public.course_memberships membership
       where membership.course_id = learning_practice_states.course_id
         and membership.student_id = learning_practice_states.student_sub
    )
  );

create policy learning_practice_sessions_own on public.learning_practice_sessions
  for all to gustav_limited
  using (student_sub = coalesce(current_setting('app.current_sub', true), ''))
  with check (student_sub = coalesce(current_setting('app.current_sub', true), ''));

create policy learning_practice_stacks_own on public.learning_practice_session_stacks
  for all to gustav_limited
  using (exists (
    select 1 from public.learning_practice_sessions session
     where session.id = learning_practice_session_stacks.session_id
       and session.student_sub = coalesce(current_setting('app.current_sub', true), '')
  ))
  with check (exists (
    select 1 from public.learning_practice_sessions session
     where session.id = learning_practice_session_stacks.session_id
       and session.student_sub = coalesce(current_setting('app.current_sub', true), '')
  ));

create policy learning_practice_items_own on public.learning_practice_session_items
  for all to gustav_limited
  using (exists (
    select 1 from public.learning_practice_sessions session
     where session.id = learning_practice_session_items.session_id
       and session.student_sub = coalesce(current_setting('app.current_sub', true), '')
  ))
  with check (exists (
    select 1 from public.learning_practice_sessions session
     where session.id = learning_practice_session_items.session_id
       and session.student_sub = coalesce(current_setting('app.current_sub', true), '')
  ));

create policy learning_practice_attempts_own on public.learning_practice_attempts
  for all to gustav_limited
  using (student_sub = coalesce(current_setting('app.current_sub', true), ''))
  with check (student_sub = coalesce(current_setting('app.current_sub', true), ''));

-- Four-argument overload: keep dependent legacy helpers intact while exposing
-- practice metadata from the same canonical modular-state function name.
create or replace function public.get_modular_unit_module_states_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_include_practice boolean
)
returns table (
  module_id uuid,
  section_id uuid,
  required_prereq_count integer,
  prereq_required integer,
  prereq_done integer,
  tasks_total integer,
  tasks_done integer,
  status text,
  module_kind text,
  due_tasks_count integer
)
language sql
stable
security invoker
set search_path = public, pg_temp
as $$
  select state.module_id,
         state.section_id,
         state.required_prereq_count,
         state.prereq_required,
         state.prereq_done,
         state.tasks_total,
         state.tasks_done,
         case
           when module.module_kind = 'practice' and state.status = 'done' then 'open'
           else state.status
         end as status,
         case when p_include_practice then module.module_kind else 'learning' end as module_kind,
         case
           when p_include_practice
             and module.module_kind = 'practice'
             and state.status in ('open', 'done')
           then (
             select count(*)::integer
               from public.unit_tasks task
               left join public.learning_practice_states practice_state
                 on practice_state.course_id = p_course_id
                and practice_state.student_sub = p_student_sub
                and practice_state.task_id = task.id
              where task.section_id = state.section_id
                and (practice_state.task_id is null or practice_state.due_at <= now())
           )
           else 0
         end as due_tasks_count
    from public.get_modular_unit_module_states_for_student(
      p_student_sub, p_course_id, p_unit_id
    ) state
    join public.unit_modules module on module.id = state.module_id;
$$;

revoke all on function public.get_modular_unit_module_states_for_student(text, uuid, uuid, boolean) from public;
grant execute on function public.get_modular_unit_module_states_for_student(text, uuid, uuid, boolean) to gustav_limited;

set check_function_bodies = on;
