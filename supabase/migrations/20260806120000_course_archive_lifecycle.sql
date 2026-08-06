-- Course lifecycle, personal learning archive and reliable export/deletion jobs.
-- Historical course records remain private; ordinary learning access continues
-- to require an active course and an active membership.

alter table public.courses
  add column if not exists school_year_start integer null,
  add column if not exists status text not null default 'active',
  add column if not exists archived_at timestamptz null,
  add column if not exists archived_by text null;

alter table public.courses drop constraint if exists courses_school_year_start_check;
alter table public.courses
  add constraint courses_school_year_start_check
  check (school_year_start is null or school_year_start between 2000 and 2200);

alter table public.courses drop constraint if exists courses_status_check;
alter table public.courses
  add constraint courses_status_check check (status in ('active', 'archived', 'deleting'));

alter table public.courses drop constraint if exists courses_archive_shape_check;
alter table public.courses
  add constraint courses_archive_shape_check check (
    (status = 'active' and archived_at is null and archived_by is null)
    or (status in ('archived', 'deleting'))
  );

create index if not exists idx_courses_teacher_status_school_year
  on public.courses(teacher_id, status, school_year_start desc, title);

alter table public.course_memberships
  add column if not exists ended_at timestamptz null,
  add column if not exists ended_by text null;

create index if not exists idx_course_memberships_student_lifecycle
  on public.course_memberships(student_id, ended_at, course_id);

create or replace function public.is_active_course_member(p_course_id uuid, p_student_sub text)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1
      from public.courses c
      join public.course_memberships m on m.course_id = c.id
     where c.id = p_course_id
       and c.status = 'active'
       and m.student_id = p_student_sub
       and m.ended_at is null
  );
$$;

revoke all on function public.is_active_course_member(uuid, text) from public;
grant execute on function public.is_active_course_member(uuid, text) to gustav_limited;

drop policy if exists courses_select_member on public.courses;
create policy courses_select_active_member on public.courses
  for select to gustav_limited
  using (public.is_active_course_member(id, coalesce(current_setting('app.current_sub', true), '')));

drop policy if exists memberships_select_self_only on public.course_memberships;
drop policy if exists memberships_select_owner_or_self on public.course_memberships;
create policy memberships_select_owner_or_active_self on public.course_memberships
  for select to gustav_limited
  using (
    public.course_exists_for_owner(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
    or (
      student_id = coalesce(current_setting('app.current_sub', true), '')
      and ended_at is null
      and public.is_active_course_member(course_id, student_id)
    )
  );

create table if not exists public.course_archive_snapshots (
  course_id uuid primary key references public.courses(id) on delete cascade,
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_at timestamptz not null default now()
);

alter table public.course_archive_snapshots enable row level security;
grant select, insert, update on public.course_archive_snapshots to gustav_limited;
create policy course_archive_snapshots_owner on public.course_archive_snapshots
  for all to gustav_limited
  using (public.course_exists_for_owner(coalesce(current_setting('app.current_sub', true), ''), course_id))
  with check (public.course_exists_for_owner(coalesce(current_setting('app.current_sub', true), ''), course_id));

create table if not exists public.learning_submission_task_snapshots (
  submission_id uuid primary key references public.learning_submissions(id) on delete cascade,
  task_snapshot jsonb not null check (jsonb_typeof(task_snapshot) = 'object'),
  created_at timestamptz not null default now()
);

alter table public.learning_submission_task_snapshots enable row level security;
grant select on public.learning_submission_task_snapshots to gustav_limited;
create policy learning_submission_task_snapshots_authorized on public.learning_submission_task_snapshots
  for select to gustav_limited
  using (
    exists (
      select 1 from public.learning_submissions s
       where s.id = submission_id
         and (
           s.student_sub = coalesce(current_setting('app.current_sub', true), '')
           or public.course_exists_for_owner(coalesce(current_setting('app.current_sub', true), ''), s.course_id)
         )
    )
  );

create or replace function public.capture_learning_submission_task_snapshot()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  insert into public.learning_submission_task_snapshots(submission_id, task_snapshot)
  select new.id,
         jsonb_strip_nulls(jsonb_build_object(
           'version', 1,
           'task_id', t.id,
           'task_kind', t.kind,
           'instruction_md', t.instruction_md,
           'criteria', to_jsonb(t.criteria),
           'unit_id', u.id,
           'unit_title', u.title,
           'section_id', s.id,
           'section_title', s.title,
           'dialog', case when t.kind = 'dialog' then (
             select jsonb_strip_nulls(jsonb_build_object(
               'partner_name', d.partner_name,
               'partner_description_md', d.partner_description_md,
               'opening_message_md', d.opening_message_md,
               'response_mode', d.response_mode,
               'max_rounds', d.max_rounds,
               'closing_prompt_md', d.closing_prompt_md
             ))
             from public.unit_task_dialog_configs d where d.task_id = t.id
           ) else null end
         ))
    from public.unit_tasks t
    join public.units u on u.id = t.unit_id
    join public.unit_sections s on s.id = t.section_id
   where t.id = new.task_id
  on conflict (submission_id) do nothing;
  return new;
end;
$$;

drop trigger if exists trg_learning_submission_task_snapshot on public.learning_submissions;
create trigger trg_learning_submission_task_snapshot
after insert on public.learning_submissions
for each row execute function public.capture_learning_submission_task_snapshot();

insert into public.learning_submission_task_snapshots(submission_id, task_snapshot)
select ls.id,
       jsonb_strip_nulls(jsonb_build_object(
         'version', 1,
         'backfilled_at', now(),
         'historical_accuracy', 'current_task_at_migration',
         'task_id', t.id,
         'task_kind', t.kind,
         'instruction_md', t.instruction_md,
         'criteria', to_jsonb(t.criteria),
         'unit_id', u.id,
         'unit_title', u.title,
         'section_id', s.id,
         'section_title', s.title
       ))
  from public.learning_submissions ls
  join public.unit_tasks t on t.id = ls.task_id
  join public.units u on u.id = t.unit_id
  join public.unit_sections s on s.id = t.section_id
on conflict (submission_id) do nothing;

create table if not exists public.learning_export_jobs (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  student_sub text not null check (length(btrim(student_sub)) > 0),
  cutoff_at timestamptz not null default now(),
  status text not null default 'pending' check (status in ('pending', 'generating', 'ready', 'failed', 'expired')),
  storage_key text null,
  size_bytes bigint null check (size_bytes is null or size_bytes > 0),
  error_code text null,
  requested_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  started_at timestamptz null,
  completed_at timestamptz null,
  retry_count integer not null default 0 check (retry_count between 0 and 5)
);

create index if not exists idx_learning_export_jobs_pending
  on public.learning_export_jobs(status, requested_at) where status in ('pending', 'generating');
create index if not exists idx_learning_export_jobs_student
  on public.learning_export_jobs(student_sub, requested_at desc);

alter table public.learning_export_jobs enable row level security;
grant select, insert on public.learning_export_jobs to gustav_limited;
create policy learning_export_jobs_select_self on public.learning_export_jobs
  for select to gustav_limited
  using (student_sub = coalesce(current_setting('app.current_sub', true), ''));
create policy learning_export_jobs_insert_self on public.learning_export_jobs
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and exists (
      select 1 from public.course_memberships m
       where m.course_id = learning_export_jobs.course_id
         and m.student_id = learning_export_jobs.student_sub
    )
  );

create table if not exists public.course_deletion_jobs (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null,
  owner_sub text not null,
  course_title text not null,
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
  impact jsonb not null default '{}'::jsonb check (jsonb_typeof(impact) = 'object'),
  retry_count integer not null default 0 check (retry_count between 0 and 20),
  error_code text null,
  created_at timestamptz not null default now(),
  started_at timestamptz null,
  completed_at timestamptz null
);

create index if not exists idx_course_deletion_jobs_pending
  on public.course_deletion_jobs(status, created_at) where status in ('pending', 'processing');

create table if not exists public.storage_deletion_outbox (
  id uuid primary key default gen_random_uuid(),
  deletion_job_id uuid not null references public.course_deletion_jobs(id) on delete cascade,
  bucket text not null,
  storage_key text not null,
  status text not null default 'pending' check (status in ('pending', 'deleted', 'failed')),
  retry_count integer not null default 0 check (retry_count between 0 and 20),
  last_error_code text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (deletion_job_id, bucket, storage_key)
);

alter table public.course_deletion_jobs enable row level security;
alter table public.storage_deletion_outbox enable row level security;
grant select on public.course_deletion_jobs to gustav_limited;
create policy course_deletion_jobs_owner_select on public.course_deletion_jobs
  for select to gustav_limited
  using (owner_sub = coalesce(current_setting('app.current_sub', true), ''));

create or replace function public.course_metadata_complete(p_course_id uuid)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select coalesce(length(btrim(subject)) > 0
    and length(btrim(grade_level)) > 0
    and school_year_start is not null, false)
  from public.courses where id = p_course_id;
$$;

create or replace function public.archive_course_owned(p_course_id uuid, p_owner_sub text)
returns public.courses
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  result public.courses;
begin
  select * into result from public.courses where id = p_course_id and teacher_id = p_owner_sub for update;
  if not found then raise exception 'course_not_found' using errcode = 'no_data_found'; end if;
  if result.status <> 'active' then raise exception 'course_not_active' using errcode = 'object_not_in_prerequisite_state'; end if;
  if not public.course_metadata_complete(p_course_id) then
    raise exception 'course_metadata_incomplete' using errcode = 'check_violation';
  end if;

  insert into public.course_archive_snapshots(course_id, snapshot)
  values (p_course_id, jsonb_build_object(
    'version', 1,
    'archived_at', now(),
    'course', to_jsonb(result),
    'modules', coalesce((select jsonb_agg(to_jsonb(cm) order by cm.position) from public.course_modules cm where cm.course_id = p_course_id), '[]'::jsonb),
    'releases', coalesce((select jsonb_agg(to_jsonb(r)) from public.module_section_releases r join public.course_modules cm on cm.id = r.course_module_id where cm.course_id = p_course_id), '[]'::jsonb)
  ))
  on conflict (course_id) do update set snapshot = excluded.snapshot, created_at = now();

  update public.learning_dialog_sessions
     set status = 'abandoned', abandoned_at = now(), updated_at = now()
   where course_id = p_course_id and status = 'active';

  update public.courses
     set status = 'archived', archived_at = now(), archived_by = p_owner_sub
   where id = p_course_id
  returning * into result;
  return result;
end;
$$;

create or replace function public.restore_course_owned(p_course_id uuid, p_owner_sub text)
returns public.courses
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare result public.courses;
begin
  update public.courses
     set status = 'active', archived_at = null, archived_by = null
   where id = p_course_id and teacher_id = p_owner_sub and status = 'archived'
  returning * into result;
  if not found then raise exception 'course_not_archived' using errcode = 'object_not_in_prerequisite_state'; end if;
  return result;
end;
$$;

revoke all on function public.archive_course_owned(uuid, text) from public;
revoke all on function public.restore_course_owned(uuid, text) from public;
grant execute on function public.archive_course_owned(uuid, text) to gustav_limited;
grant execute on function public.restore_course_owned(uuid, text) to gustav_limited;

-- Ordinary application roles must never bypass the strongly confirmed job.
revoke delete on public.courses from gustav_limited;
drop policy if exists courses_delete_owner on public.courses;

do $$
begin
  if exists (select 1 from information_schema.schemata where schema_name = 'storage') then
    insert into storage.buckets(id, name, public)
    values ('learning-exports', 'learning-exports', false)
    on conflict (id) do update set public = false;
  end if;
end $$;
