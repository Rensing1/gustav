-- Teaching/Learning: AI dialog task configuration, resumable sessions and turns.
--
-- Why:
--   Dialog work is mutable until final submission, while the resulting
--   learning_submission remains immutable. Internal teacher instructions are
--   stored separately from learner-visible session and turn rows.

set check_function_bodies = off;

create or replace function public.dialog_sentence_starters_valid(p_values text[])
returns boolean
language sql
immutable
set search_path = pg_catalog, public
as $$
  select coalesce(
    cardinality(p_values) <= 3
    and not exists (
      select 1 from unnest(p_values) as value
       where length(btrim(value)) not between 1 and 240
    ),
    false
  )
$$;

alter table public.unit_tasks drop constraint if exists unit_tasks_kind_check;
alter table public.unit_tasks
  add constraint unit_tasks_kind_check
  check (kind in ('native', 'h5p', 'visual', 'scratch', 'calliope', 'filius', 'dialog'));

create table if not exists public.unit_task_dialog_configs (
  task_id uuid primary key references public.unit_tasks(id) on delete cascade,
  partner_name text not null check (length(btrim(partner_name)) between 1 and 120),
  partner_description_md text not null check (length(btrim(partner_description_md)) between 1 and 2000),
  role_md text not null check (length(btrim(role_md)) between 1 and 4000),
  learning_goal_md text not null check (length(btrim(learning_goal_md)) between 1 and 2000),
  opening_message_md text not null check (length(btrim(opening_message_md)) between 1 and 2000),
  response_mode text not null check (response_mode in ('free_text', 'hybrid')),
  max_rounds integer not null default 8 check (max_rounds between 1 and 12),
  closing_prompt_md text null check (
    closing_prompt_md is null or length(btrim(closing_prompt_md)) between 1 and 2000
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_unit_task_dialog_configs_updated_at on public.unit_task_dialog_configs;
create trigger trg_unit_task_dialog_configs_updated_at
before update on public.unit_task_dialog_configs
for each row execute function public.set_updated_at();

alter table public.unit_task_dialog_configs enable row level security;
grant select, insert, update, delete on public.unit_task_dialog_configs to gustav_limited;

create policy unit_task_dialog_configs_select_author on public.unit_task_dialog_configs
  for select to gustav_limited
  using (
    exists (
      select 1
        from public.unit_tasks t
        join public.units u on u.id = t.unit_id
       where t.id = task_id
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_task_dialog_configs_insert_author on public.unit_task_dialog_configs
  for insert to gustav_limited
  with check (
    exists (
      select 1
        from public.unit_tasks t
        join public.units u on u.id = t.unit_id
       where t.id = task_id
         and t.kind = 'dialog'
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_task_dialog_configs_update_author on public.unit_task_dialog_configs
  for update to gustav_limited
  using (
    exists (
      select 1
        from public.unit_tasks t
        join public.units u on u.id = t.unit_id
       where t.id = task_id
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1
        from public.unit_tasks t
        join public.units u on u.id = t.unit_id
       where t.id = task_id
         and t.kind = 'dialog'
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_task_dialog_configs_delete_author on public.unit_task_dialog_configs
  for delete to gustav_limited
  using (
    exists (
      select 1
        from public.unit_tasks t
        join public.units u on u.id = t.unit_id
       where t.id = task_id
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create table if not exists public.learning_dialog_sessions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  student_sub text not null check (length(btrim(student_sub)) > 0),
  status text not null default 'active' check (status in ('active', 'completed', 'abandoned')),
  round_count integer not null default 0 check (round_count between 0 and 12),
  initial_sentence_starters text[] not null default '{}',
  initial_starters_status text not null default 'not_required'
    check (initial_starters_status in ('not_required', 'pending', 'generating', 'completed', 'failed')),
  initial_starters_error_code text null,
  initial_generation_attempts integer not null default 0 check (initial_generation_attempts between 0 and 3),
  closing_answer_md text null check (
    closing_answer_md is null or length(btrim(closing_answer_md)) between 1 and 2000
  ),
  completion_idempotency_key text null check (
    completion_idempotency_key is null or completion_idempotency_key ~ '^[A-Za-z0-9_-]{1,64}$'
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz null,
  abandoned_at timestamptz null,
  constraint learning_dialog_sessions_initial_starters_count
    check (public.dialog_sentence_starters_valid(initial_sentence_starters))
);

create unique index if not exists idx_learning_dialog_sessions_one_active
  on public.learning_dialog_sessions(course_id, task_id, student_sub)
  where status = 'active';

create unique index if not exists idx_learning_dialog_sessions_completion_key
  on public.learning_dialog_sessions(course_id, task_id, student_sub, completion_idempotency_key)
  where completion_idempotency_key is not null;

create index if not exists idx_learning_dialog_sessions_student_task
  on public.learning_dialog_sessions(student_sub, course_id, task_id, created_at desc);

drop trigger if exists trg_learning_dialog_sessions_updated_at on public.learning_dialog_sessions;
create trigger trg_learning_dialog_sessions_updated_at
before update on public.learning_dialog_sessions
for each row execute function public.set_updated_at();

create table if not exists public.learning_dialog_session_contexts (
  session_id uuid primary key references public.learning_dialog_sessions(id) on delete cascade,
  instruction_md text not null,
  criteria text[] not null default '{}',
  teacher_context_md text null,
  max_attempts integer null check (max_attempts is null or max_attempts > 0),
  dialog_config jsonb not null check (jsonb_typeof(dialog_config) = 'object'),
  created_at timestamptz not null default now()
);

create or replace function public.learning_dialog_context_immutable()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  raise exception 'dialog session context is immutable' using errcode = 'check_violation';
end;
$$;

drop trigger if exists trg_learning_dialog_context_immutable on public.learning_dialog_session_contexts;
create trigger trg_learning_dialog_context_immutable
before update on public.learning_dialog_session_contexts
for each row execute function public.learning_dialog_context_immutable();

create table if not exists public.learning_dialog_turns (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.learning_dialog_sessions(id) on delete cascade,
  round_nr integer not null check (round_nr between 1 and 12),
  student_message_md text not null check (length(btrim(student_message_md)) between 1 and 2000),
  used_sentence_starter_md text null check (
    used_sentence_starter_md is null or length(btrim(used_sentence_starter_md)) between 1 and 240
  ),
  used_sentence_starter_source text null check (
    used_sentence_starter_source is null or length(btrim(used_sentence_starter_source)) between 1 and 80
  ),
  status text not null default 'generating' check (status in ('generating', 'completed', 'failed')),
  assistant_reply_md text null check (
    assistant_reply_md is null or length(btrim(assistant_reply_md)) between 1 and 2000
  ),
  sentence_starters text[] not null default '{}',
  generation_attempts integer not null default 1 check (generation_attempts between 1 and 3),
  error_code text null,
  idempotency_key text not null check (idempotency_key ~ '^[A-Za-z0-9_-]{1,64}$'),
  generation_started_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  completed_at timestamptz null,
  unique (session_id, round_nr),
  unique (session_id, idempotency_key),
  constraint learning_dialog_turns_starters_count check (public.dialog_sentence_starters_valid(sentence_starters)),
  constraint learning_dialog_turns_starter_provenance check (
    (used_sentence_starter_md is null and used_sentence_starter_source is null)
    or (used_sentence_starter_md is not null and used_sentence_starter_source is not null)
  ),
  constraint learning_dialog_turns_completed_shape check (
    (status = 'completed' and assistant_reply_md is not null and completed_at is not null and error_code is null)
    or (status = 'generating' and assistant_reply_md is null and completed_at is null)
    or (status = 'failed' and assistant_reply_md is null and completed_at is null and error_code is not null)
  )
);

create or replace function public.learning_dialog_turn_student_content_immutable()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
  if new.session_id <> old.session_id
     or new.round_nr <> old.round_nr
     or new.student_message_md <> old.student_message_md
     or new.used_sentence_starter_md is distinct from old.used_sentence_starter_md
     or new.used_sentence_starter_source is distinct from old.used_sentence_starter_source
     or new.idempotency_key <> old.idempotency_key then
    raise exception 'dialog learner message is immutable' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_learning_dialog_turn_student_content_immutable on public.learning_dialog_turns;
create trigger trg_learning_dialog_turn_student_content_immutable
before update on public.learning_dialog_turns
for each row execute function public.learning_dialog_turn_student_content_immutable();

create table if not exists public.dialog_ai_usage_events (
  id uuid primary key default gen_random_uuid(),
  event_key uuid not null unique,
  occurred_at timestamptz not null default now(),
  session_id uuid null references public.learning_dialog_sessions(id) on delete cascade,
  course_id uuid null references public.courses(id) on delete cascade,
  unit_id uuid not null references public.units(id) on delete cascade,
  task_id uuid not null references public.unit_tasks(id) on delete cascade,
  actor_sub text not null check (length(btrim(actor_sub)) > 0),
  actor_role text not null check (actor_role in ('student', 'teacher')),
  stage text not null check (stage in ('initial_starters', 'reply', 'preview')),
  model text not null check (length(btrim(model)) > 0),
  usage_known boolean not null,
  input_tokens integer null check (input_tokens is null or input_tokens >= 0),
  output_tokens integer null check (output_tokens is null or output_tokens >= 0),
  total_tokens integer null check (total_tokens is null or total_tokens >= 0),
  unknown_reason text null,
  error_code text null check (error_code is null or error_code = 'dialog_ai_unavailable'),
  constraint dialog_ai_usage_events_context check (
    (actor_role = 'student' and session_id is not null and course_id is not null)
    or (actor_role = 'teacher' and session_id is null)
  ),
  constraint dialog_ai_usage_events_usage_shape check (
    (usage_known and unknown_reason is null and (input_tokens is not null or output_tokens is not null or total_tokens is not null))
    or (not usage_known and input_tokens is null and output_tokens is null and total_tokens is null and unknown_reason = 'missing_provider_usage')
  )
);

create index if not exists idx_dialog_ai_usage_course_occurred
  on public.dialog_ai_usage_events(course_id, occurred_at desc);
create index if not exists idx_dialog_ai_usage_task_occurred
  on public.dialog_ai_usage_events(task_id, occurred_at desc);

alter table public.learning_submissions
  add column if not exists dialog_session_id uuid null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.learning_submissions'::regclass
       and conname = 'learning_submissions_dialog_session_id_fkey'
  ) then
    alter table public.learning_submissions
      add constraint learning_submissions_dialog_session_id_fkey
      foreign key (dialog_session_id) references public.learning_dialog_sessions(id) on delete cascade;
  end if;
end $$;

create unique index if not exists idx_learning_submissions_dialog_session
  on public.learning_submissions(dialog_session_id)
  where dialog_session_id is not null;

alter table public.learning_submissions drop constraint if exists learning_submissions_kind_check;
alter table public.learning_submissions
  add constraint learning_submissions_kind_check
  check (kind in ('text', 'image', 'file', 'h5p', 'dialog'));

alter table public.learning_submissions drop constraint if exists learning_submissions_dialog_kind;
alter table public.learning_submissions
  add constraint learning_submissions_dialog_kind
  check (
    (kind = 'dialog' and dialog_session_id is not null and text_body is null
      and storage_key is null and mime_type is null and size_bytes is null and sha256 is null
      and score_raw is null and score_max is null)
    or (kind <> 'dialog' and dialog_session_id is null)
  );

alter table public.learning_dialog_sessions enable row level security;
alter table public.learning_dialog_session_contexts enable row level security;
alter table public.learning_dialog_turns enable row level security;
alter table public.dialog_ai_usage_events enable row level security;

grant select, insert, update on public.learning_dialog_sessions to gustav_limited;
grant select, insert, update on public.learning_dialog_turns to gustav_limited;
grant select, insert on public.dialog_ai_usage_events to gustav_limited;
revoke all on public.learning_dialog_session_contexts from public, gustav_limited;

create policy learning_dialog_sessions_select_authorized on public.learning_dialog_sessions
  for select to gustav_limited
  using (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    or (
      status = 'completed'
      and exists (
        select 1 from public.courses c
         where c.id = course_id
           and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
      )
    )
  );

create policy learning_dialog_sessions_insert_self on public.learning_dialog_sessions
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and public.check_task_visible_to_student(student_sub, course_id, task_id)
    and exists (select 1 from public.unit_tasks t where t.id = task_id and t.kind = 'dialog')
  );

create policy learning_dialog_sessions_update_self on public.learning_dialog_sessions
  for update to gustav_limited
  using (student_sub = coalesce(current_setting('app.current_sub', true), '') and status = 'active')
  with check (student_sub = coalesce(current_setting('app.current_sub', true), ''));

create policy learning_dialog_turns_select_authorized on public.learning_dialog_turns
  for select to gustav_limited
  using (
    exists (
      select 1 from public.learning_dialog_sessions s
       where s.id = session_id
         and (
           s.student_sub = coalesce(current_setting('app.current_sub', true), '')
           or (
             s.status = 'completed'
             and exists (
               select 1 from public.courses c
                where c.id = s.course_id
                  and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
             )
           )
         )
    )
  );

create policy learning_dialog_turns_insert_self on public.learning_dialog_turns
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.learning_dialog_sessions s
       where s.id = session_id
         and s.status = 'active'
         and s.student_sub = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy learning_dialog_turns_update_self on public.learning_dialog_turns
  for update to gustav_limited
  using (
    exists (
      select 1 from public.learning_dialog_sessions s
       where s.id = session_id
         and s.status = 'active'
         and s.student_sub = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1 from public.learning_dialog_sessions s
       where s.id = session_id
         and s.status = 'active'
         and s.student_sub = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy dialog_ai_usage_events_select_owner on public.dialog_ai_usage_events
  for select to gustav_limited
  using (
    exists (
      select 1 from public.units u
       where u.id = unit_id
         and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
    or exists (
      select 1 from public.courses c
       where c.id = course_id
         and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy dialog_ai_usage_events_insert_scoped on public.dialog_ai_usage_events
  for insert to gustav_limited
  with check (
    actor_sub = coalesce(current_setting('app.current_sub', true), '')
    and (
      (
        actor_role = 'student'
        and exists (
          select 1 from public.learning_dialog_sessions s
           where s.id = session_id and s.course_id = course_id
             and s.task_id = task_id and s.student_sub = actor_sub
        )
      )
      or (
        actor_role = 'teacher'
        and exists (
          select 1 from public.units u
           where u.id = unit_id and u.author_id = actor_sub
        )
      )
    )
  );

create or replace function public.learning_start_dialog_session(
  p_course_id uuid,
  p_task_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_student_sub text := coalesce(current_setting('app.current_sub', true), '');
  v_existing uuid;
  v_task record;
  v_session_id uuid;
  v_final_count integer;
begin
  if v_student_sub = '' then
    raise exception 'dialog_session_forbidden' using errcode = 'insufficient_privilege';
  end if;

  select id into v_existing
    from public.learning_dialog_sessions
   where course_id = p_course_id
     and task_id = p_task_id
     and student_sub = v_student_sub
     and status = 'active';
  if found then
    return v_existing;
  end if;

  if not public.check_task_visible_to_student(v_student_sub, p_course_id, p_task_id) then
    raise exception 'dialog_task_not_visible' using errcode = 'no_data_found';
  end if;

  select t.instruction_md, t.criteria, t.teacher_context_md, t.max_attempts,
         jsonb_build_object(
           'partner_name', d.partner_name,
           'partner_description_md', d.partner_description_md,
           'role_md', d.role_md,
           'learning_goal_md', d.learning_goal_md,
           'opening_message_md', d.opening_message_md,
           'response_mode', d.response_mode,
           'max_rounds', d.max_rounds,
           'closing_prompt_md', d.closing_prompt_md
         ) as dialog_config
    into v_task
    from public.unit_tasks t
    join public.unit_task_dialog_configs d on d.task_id = t.id
   where t.id = p_task_id and t.kind = 'dialog';
  if not found then
    raise exception 'invalid_dialog_task' using errcode = 'check_violation';
  end if;

  select count(*) into v_final_count
    from public.learning_submissions
   where course_id = p_course_id
     and task_id = p_task_id
     and student_sub = v_student_sub
     and intent = 'submit'
     and kind = 'dialog';
  if v_task.max_attempts is not null and v_final_count >= v_task.max_attempts then
    raise exception 'max_attempts_exceeded' using errcode = 'check_violation';
  end if;

  insert into public.learning_dialog_sessions (
    course_id, task_id, student_sub, initial_starters_status
  ) values (
    p_course_id,
    p_task_id,
    v_student_sub,
    case when v_task.dialog_config->>'response_mode' = 'hybrid' then 'pending' else 'not_required' end
  )
  on conflict (course_id, task_id, student_sub) where status = 'active'
  do nothing
  returning id into v_session_id;

  if v_session_id is null then
    select id into v_session_id
      from public.learning_dialog_sessions
     where course_id = p_course_id and task_id = p_task_id
       and student_sub = v_student_sub and status = 'active';
    return v_session_id;
  end if;

  insert into public.learning_dialog_session_contexts (
    session_id, instruction_md, criteria, teacher_context_md, max_attempts, dialog_config
  ) values (
    v_session_id, v_task.instruction_md, v_task.criteria, v_task.teacher_context_md,
    v_task.max_attempts, v_task.dialog_config
  );

  return v_session_id;
end;
$$;

revoke all on function public.learning_start_dialog_session(uuid, uuid) from public;
grant execute on function public.learning_start_dialog_session(uuid, uuid) to gustav_limited;

create or replace function public.learning_get_dialog_context(
  p_course_id uuid,
  p_task_id uuid,
  p_session_id uuid
)
returns table (
  instruction_md text,
  criteria text[],
  teacher_context_md text,
  max_attempts integer,
  dialog_config jsonb
)
language sql
security definer
set search_path = pg_catalog, public
as $$
  select c.instruction_md, c.criteria, c.teacher_context_md, c.max_attempts, c.dialog_config
    from public.learning_dialog_sessions s
    join public.learning_dialog_session_contexts c on c.session_id = s.id
   where s.id = p_session_id
     and s.course_id = p_course_id
     and s.task_id = p_task_id
     and s.student_sub = coalesce(current_setting('app.current_sub', true), '')
$$;

revoke all on function public.learning_get_dialog_context(uuid, uuid, uuid) from public;
grant execute on function public.learning_get_dialog_context(uuid, uuid, uuid) to gustav_limited;

create or replace function public.learning_get_visible_dialog_configs(
  p_student_sub text,
  p_course_id uuid,
  p_task_ids uuid[]
)
returns table (
  task_id uuid,
  partner_name text,
  partner_description_md text,
  opening_message_md text,
  response_mode text,
  max_rounds integer,
  closing_prompt_md text,
  active_session_id uuid
)
language sql
security definer
set search_path = pg_catalog, public
as $$
  select d.task_id, d.partner_name, d.partner_description_md,
         d.opening_message_md, d.response_mode, d.max_rounds,
         d.closing_prompt_md, s.id
    from public.unit_task_dialog_configs d
    join public.unit_tasks t on t.id = d.task_id and t.kind = 'dialog'
    left join public.learning_dialog_sessions s
      on s.task_id = d.task_id
     and s.course_id = p_course_id
     and s.student_sub = p_student_sub
     and s.status = 'active'
   where p_student_sub = coalesce(current_setting('app.current_sub', true), '')
     and d.task_id = any(p_task_ids)
     and public.check_task_visible_to_student(p_student_sub, p_course_id, d.task_id)
$$;

revoke all on function public.learning_get_visible_dialog_configs(text, uuid, uuid[]) from public;
grant execute on function public.learning_get_visible_dialog_configs(text, uuid, uuid[]) to gustav_limited;

create or replace function public.teaching_get_dialog_submission(
  p_course_id uuid,
  p_unit_id uuid,
  p_task_id uuid,
  p_student_sub text,
  p_submission_id uuid
)
returns jsonb
language sql
security definer
set search_path = pg_catalog, public
as $$
  select jsonb_build_object(
    'id', s.id,
    'course_id', s.course_id,
    'task_id', s.task_id,
    'status', s.status,
    'round_count', s.round_count,
    'partner_name', c.dialog_config->>'partner_name',
    'partner_description_md', c.dialog_config->>'partner_description_md',
    'opening_message_md', c.dialog_config->>'opening_message_md',
    'response_mode', c.dialog_config->>'response_mode',
    'max_rounds', (c.dialog_config->>'max_rounds')::integer,
    'closing_prompt_md', c.dialog_config->'closing_prompt_md',
    'closing_answer_md', s.closing_answer_md,
    'initial_starters', to_jsonb(s.initial_sentence_starters),
    'initial_generation_status', s.initial_starters_status,
    'created_at', s.created_at,
    'updated_at', s.updated_at,
    'completed_at', s.completed_at,
    'turns', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', t.id,
        'round_nr', t.round_nr,
        'student_message', t.student_message_md,
        'starter_text', t.used_sentence_starter_md,
        'starter_source', t.used_sentence_starter_source,
        'status', t.status,
        'ai_message', t.assistant_reply_md,
        'next_starters', to_jsonb(t.sentence_starters),
        'generation_attempts', t.generation_attempts,
        'created_at', t.created_at,
        'completed_at', t.completed_at
      ) order by t.round_nr)
      from public.learning_dialog_turns t where t.session_id = s.id
    ), '[]'::jsonb)
  )
    from public.learning_submissions ls
    join public.learning_dialog_sessions s on s.id = ls.dialog_session_id
    join public.learning_dialog_session_contexts c on c.session_id = s.id
    join public.courses course on course.id = ls.course_id
    join public.unit_tasks task on task.id = ls.task_id
   where ls.id = p_submission_id
     and ls.kind = 'dialog'
     and ls.course_id = p_course_id
     and ls.task_id = p_task_id
     and ls.student_sub = p_student_sub
     and task.unit_id = p_unit_id
     and course.teacher_id = coalesce(current_setting('app.current_sub', true), '')
$$;

revoke all on function public.teaching_get_dialog_submission(uuid, uuid, uuid, text, uuid) from public;
grant execute on function public.teaching_get_dialog_submission(uuid, uuid, uuid, text, uuid) to gustav_limited;

set check_function_bodies = on;
