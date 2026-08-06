-- Security-definer read and command boundaries for former memberships,
-- personal exports and strongly confirmed deletion jobs.

create or replace function public.list_personal_courses(
  p_student_sub text,
  p_scope text default 'current',
  p_limit integer default 50,
  p_offset integer default 0
)
returns table(
  id uuid,
  title text,
  subject text,
  grade_level text,
  term text,
  school_year_start integer,
  status text,
  membership_status text
)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select c.id, c.title, c.subject, c.grade_level, c.term, c.school_year_start,
         case when c.status = 'archived' then 'archived' else 'active' end,
         case when m.ended_at is null then 'active' else 'former' end
    from public.courses c
    join public.course_memberships m on m.course_id = c.id
   where p_student_sub = coalesce(current_setting('app.current_sub', true), '')
     and m.student_id = p_student_sub
     and c.status <> 'deleting'
     and (
       (p_scope = 'current' and c.status = 'active' and m.ended_at is null)
       or (p_scope = 'past' and (c.status = 'archived' or m.ended_at is not null))
     )
   order by c.school_year_start desc nulls last, c.title asc, c.id asc
   offset greatest(p_offset, 0)
   limit least(greatest(p_limit, 1), 100);
$$;

revoke all on function public.list_personal_courses(text, text, integer, integer) from public;
grant execute on function public.list_personal_courses(text, text, integer, integer) to gustav_limited;

create or replace function public.personal_course_portfolio(
  p_course_id uuid,
  p_student_sub text
)
returns table(
  submission_id uuid,
  kind text,
  intent text,
  created_at timestamptz,
  completed_at timestamptz,
  text_body text,
  feedback_md text,
  analysis_json jsonb,
  storage_key text,
  mime_type text,
  dialog_session_id uuid,
  task_snapshot jsonb
)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select s.id, s.kind, s.intent, s.created_at, s.completed_at, s.text_body,
         s.feedback_md, s.analysis_json, s.storage_key,
         s.mime_type, s.dialog_session_id, snap.task_snapshot
    from public.learning_submissions s
    join public.course_memberships m
      on m.course_id = s.course_id and m.student_id = p_student_sub
    join public.courses c on c.id = s.course_id and c.status <> 'deleting'
    join public.learning_submission_task_snapshots snap on snap.submission_id = s.id
   where p_student_sub = coalesce(current_setting('app.current_sub', true), '')
     and s.course_id = p_course_id
     and s.student_sub = p_student_sub
     and (s.intent = 'submit' or s.feedback_md is not null)
   order by s.created_at desc, s.id desc;
$$;

revoke all on function public.personal_course_portfolio(uuid, text) from public;
grant execute on function public.personal_course_portfolio(uuid, text) to gustav_limited;

create or replace function public.create_learning_export_job_owned(
  p_course_id uuid,
  p_student_sub text
)
returns public.learning_export_jobs
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare result public.learning_export_jobs;
begin
  if p_student_sub <> coalesce(current_setting('app.current_sub', true), '') then
    raise exception 'forbidden' using errcode = 'insufficient_privilege';
  end if;
  if not exists (
    select 1 from public.course_memberships m
    join public.courses c on c.id = m.course_id
    where m.course_id = p_course_id and m.student_id = p_student_sub and c.status <> 'deleting'
  ) then
    raise exception 'not_found' using errcode = 'no_data_found';
  end if;
  insert into public.learning_export_jobs(course_id, student_sub)
  values (p_course_id, p_student_sub)
  returning * into result;
  return result;
end;
$$;

revoke all on function public.create_learning_export_job_owned(uuid, text) from public;
grant execute on function public.create_learning_export_job_owned(uuid, text) to gustav_limited;
revoke insert on public.learning_export_jobs from gustav_limited;
drop policy if exists learning_export_jobs_insert_self on public.learning_export_jobs;

create or replace function public.course_deletion_impact_owned(p_course_id uuid, p_owner_sub text)
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select jsonb_build_object(
    'course_id', c.id,
    'title', c.title,
    'members_count', (select count(*) from public.course_memberships m where m.course_id = c.id),
    'submissions_count', (select count(*) from public.learning_submissions s where s.course_id = c.id),
    'dialogs_count', (select count(*) from public.learning_dialog_sessions d where d.course_id = c.id),
    'files_count',
      (select count(*) from public.learning_submissions s where s.course_id = c.id and s.storage_key is not null)
      + (select count(*) from public.learning_export_jobs e where e.course_id = c.id and e.storage_key is not null)
  )
  from public.courses c
  where c.id = p_course_id and c.teacher_id = p_owner_sub and c.status <> 'deleting';
$$;

create or replace function public.queue_course_deletion_owned(
  p_course_id uuid,
  p_owner_sub text,
  p_confirmation_title text,
  p_confirm_student_data_loss boolean
)
returns public.course_deletion_jobs
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  course_row public.courses;
  impact_row jsonb;
  result public.course_deletion_jobs;
begin
  select * into course_row from public.courses
   where id = p_course_id and teacher_id = p_owner_sub and status <> 'deleting'
   for update;
  if not found then raise exception 'course_not_found' using errcode = 'no_data_found'; end if;
  if not p_confirm_student_data_loss or p_confirmation_title <> course_row.title then
    raise exception 'deletion_confirmation_mismatch' using errcode = 'check_violation';
  end if;

  impact_row := public.course_deletion_impact_owned(p_course_id, p_owner_sub);
  insert into public.course_deletion_jobs(course_id, owner_sub, course_title, impact)
  values (p_course_id, p_owner_sub, course_row.title, impact_row)
  returning * into result;

  insert into public.storage_deletion_outbox(deletion_job_id, bucket, storage_key)
  select result.id, 'submissions', s.storage_key
    from public.learning_submissions s
   where s.course_id = p_course_id and s.storage_key is not null
  on conflict do nothing;

  insert into public.storage_deletion_outbox(deletion_job_id, bucket, storage_key)
  select result.id, 'learning-exports', e.storage_key
    from public.learning_export_jobs e
   where e.course_id = p_course_id and e.storage_key is not null
  on conflict do nothing;

  update public.courses set status = 'deleting' where id = p_course_id;
  return result;
end;
$$;

revoke all on function public.course_deletion_impact_owned(uuid, text) from public;
revoke all on function public.queue_course_deletion_owned(uuid, text, text, boolean) from public;
grant execute on function public.course_deletion_impact_owned(uuid, text) to gustav_limited;
grant execute on function public.queue_course_deletion_owned(uuid, text, text, boolean) to gustav_limited;

create or replace function public.finalize_course_deletion(p_job_id uuid)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare target_course_id uuid;
begin
  if exists (
    select 1 from public.storage_deletion_outbox
     where deletion_job_id = p_job_id and status <> 'deleted'
  ) then return false; end if;
  select course_id into target_course_id from public.course_deletion_jobs where id = p_job_id for update;
  if target_course_id is null then return false; end if;
  delete from public.courses where id = target_course_id and status = 'deleting';
  update public.course_deletion_jobs set status = 'completed', completed_at = now(), error_code = null where id = p_job_id;
  return true;
end;
$$;

revoke all on function public.finalize_course_deletion(uuid) from public;
grant execute on function public.finalize_course_deletion(uuid) to gustav_worker;
grant select, update on public.course_deletion_jobs, public.storage_deletion_outbox, public.learning_export_jobs to gustav_worker;
