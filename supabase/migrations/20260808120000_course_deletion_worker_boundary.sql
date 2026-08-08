-- Reliable, least-privilege lifecycle jobs for course deletion and export cleanup.

set check_function_bodies = off;

alter table public.storage_deletion_outbox
  drop constraint if exists storage_deletion_outbox_status_check;
alter table public.storage_deletion_outbox
  add constraint storage_deletion_outbox_status_check
  check (status in ('pending', 'processing', 'deleted', 'failed'));
alter table public.storage_deletion_outbox
  add column if not exists lease_token uuid null,
  add column if not exists leased_until timestamptz null,
  add column if not exists next_attempt_at timestamptz not null default now();

alter table public.learning_export_jobs
  add column if not exists cleanup_lease_token uuid null,
  add column if not exists cleanup_leased_until timestamptz null,
  add column if not exists cleanup_next_attempt_at timestamptz not null default now(),
  add column if not exists cleanup_retry_count integer not null default 0
    check (cleanup_retry_count between 0 and 20),
  add column if not exists cleanup_last_error_code text null;

create unique index if not exists idx_course_deletion_jobs_one_open_per_course
  on public.course_deletion_jobs(course_id)
  where status in ('pending', 'processing', 'failed');
create index if not exists idx_storage_deletion_outbox_claim
  on public.storage_deletion_outbox(next_attempt_at, created_at)
  where status in ('pending', 'processing', 'failed');
create index if not exists idx_learning_export_jobs_cleanup_claim
  on public.learning_export_jobs(cleanup_next_attempt_at, expires_at)
  where status <> 'expired';

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
  result public.course_deletion_jobs;
  impact_row jsonb;
begin
  if p_owner_sub <> coalesce(current_setting('app.current_sub', true), '') then
    raise exception 'forbidden' using errcode = 'insufficient_privilege';
  end if;

  select * into course_row
    from public.courses
   where id = p_course_id and teacher_id = p_owner_sub
   for update;

  if not found then
    select * into result
      from public.course_deletion_jobs
     where course_id = p_course_id and owner_sub = p_owner_sub
     order by created_at desc, id desc
     limit 1;
    if not found then
      raise exception 'course_not_found' using errcode = 'no_data_found';
    end if;
    if not p_confirm_student_data_loss or p_confirmation_title <> result.course_title then
      raise exception 'deletion_confirmation_mismatch' using errcode = 'check_violation';
    end if;
    return result;
  end if;

  if not p_confirm_student_data_loss or p_confirmation_title <> course_row.title then
    raise exception 'deletion_confirmation_mismatch' using errcode = 'check_violation';
  end if;

  if course_row.status = 'deleting' then
    select * into result
      from public.course_deletion_jobs
     where course_id = p_course_id
       and owner_sub = p_owner_sub
       and status in ('pending', 'processing', 'failed')
     order by created_at desc, id desc
     limit 1
     for update;
    if not found then
      raise exception 'course_already_deleting' using errcode = 'object_not_in_prerequisite_state';
    end if;
    if result.status = 'failed' then
      update public.storage_deletion_outbox
         set status = case when status = 'deleted' then 'deleted' else 'pending' end,
             retry_count = case when status = 'deleted' then retry_count else 0 end,
             lease_token = null,
             leased_until = null,
             next_attempt_at = now(),
             last_error_code = null,
             updated_at = now()
       where deletion_job_id = result.id;
      update public.course_deletion_jobs
         set status = 'pending', retry_count = 0, error_code = null,
             started_at = null, completed_at = null
       where id = result.id
       returning * into result;
    end if;
    return result;
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

create or replace function public.guard_course_mutation()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  target_course_id uuid;
  target_status text;
begin
  if tg_table_name = 'course_memberships' then
    target_course_id := coalesce(new.course_id, old.course_id);
  elsif tg_table_name = 'course_modules' then
    target_course_id := coalesce(new.course_id, old.course_id);
  elsif tg_table_name = 'module_section_releases' then
    select cm.course_id into target_course_id
      from public.course_modules cm
     where cm.id = coalesce(new.course_module_id, old.course_module_id);
  end if;

  select status into target_status from public.courses where id = target_course_id;
  if tg_op = 'DELETE'
     and target_status = 'deleting'
     and session_user = 'gustav_worker' then
    return old;
  end if;
  if target_status <> 'active' then
    raise exception 'course_archived' using errcode = 'object_not_in_prerequisite_state';
  end if;
  if not public.course_metadata_complete(target_course_id) then
    raise exception 'course_metadata_incomplete' using errcode = 'check_violation';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create or replace function public.finalize_course_deletion(p_job_id uuid)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  target_course_id uuid;
begin
  if exists (
    select 1 from public.storage_deletion_outbox
     where deletion_job_id = p_job_id and status <> 'deleted'
  ) then
    return false;
  end if;

  select course_id into target_course_id
    from public.course_deletion_jobs
   where id = p_job_id and status in ('pending', 'processing')
   for update;
  if target_course_id is null then
    return false;
  end if;

  delete from public.courses
   where id = target_course_id and status = 'deleting';
  if not found and exists (select 1 from public.courses where id = target_course_id) then
    return false;
  end if;

  update public.course_deletion_jobs
     set status = 'completed', completed_at = now(), error_code = null
   where id = p_job_id;
  return true;
end;
$$;

create or replace function public.learning_worker_claim_course_deletion()
returns table(
  action text,
  job_id uuid,
  outbox_id uuid,
  bucket text,
  storage_key text,
  lease_token uuid
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  selected_job_id uuid;
  selected_outbox_id uuid;
  selected_bucket text;
  selected_storage_key text;
  selected_lease_token uuid;
begin
  select j.id into selected_job_id
    from public.course_deletion_jobs j
   where j.status in ('pending', 'processing')
     and not exists (
       select 1 from public.storage_deletion_outbox o
        where o.deletion_job_id = j.id and o.status <> 'deleted'
     )
   order by j.created_at, j.id
   for update skip locked
   limit 1;
  if selected_job_id is not null then
    update public.course_deletion_jobs
       set status = 'processing', started_at = coalesce(started_at, now())
     where id = selected_job_id;
    perform public.finalize_course_deletion(selected_job_id);
    action := 'finalized';
    job_id := selected_job_id;
    return next;
    return;
  end if;

  select j.id, o.id, o.bucket, o.storage_key
    into selected_job_id, selected_outbox_id, selected_bucket, selected_storage_key
    from public.course_deletion_jobs j
    join public.storage_deletion_outbox o on o.deletion_job_id = j.id
   where j.status in ('pending', 'processing')
     and (
       o.status = 'pending'
       or (o.status = 'failed' and o.retry_count < 20 and o.next_attempt_at <= now())
       or (o.status = 'processing' and o.leased_until <= now())
     )
   order by j.created_at, o.created_at, o.id
   for update of j, o skip locked
   limit 1;

  if selected_outbox_id is not null then
    selected_lease_token := gen_random_uuid();
    update public.course_deletion_jobs
       set status = 'processing', started_at = coalesce(started_at, now())
     where id = selected_job_id;
    update public.storage_deletion_outbox
       set status = 'processing', lease_token = selected_lease_token,
           leased_until = now() + interval '90 seconds', updated_at = now()
     where id = selected_outbox_id;
    action := 'delete_object';
    job_id := selected_job_id;
    outbox_id := selected_outbox_id;
    bucket := selected_bucket;
    storage_key := selected_storage_key;
    lease_token := selected_lease_token;
    return next;
    return;
  end if;

  select j.id into selected_job_id
    from public.course_deletion_jobs j
   where j.status in ('pending', 'processing')
     and exists (
       select 1 from public.storage_deletion_outbox o
        where o.deletion_job_id = j.id
          and o.status = 'failed'
          and o.retry_count >= 20
     )
   order by j.created_at, j.id
   for update skip locked
   limit 1;
  if selected_job_id is not null then
    update public.course_deletion_jobs
       set status = 'failed', error_code = 'storage_delete_failed', completed_at = now()
     where id = selected_job_id;
    action := 'failed';
    job_id := selected_job_id;
    return next;
  end if;
end;
$$;

create or replace function public.learning_worker_complete_storage_deletion(
  p_outbox_id uuid,
  p_lease_token uuid
)
returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $$
  update public.storage_deletion_outbox
     set status = 'deleted', lease_token = null, leased_until = null,
         last_error_code = null, updated_at = now()
   where id = p_outbox_id
     and status = 'processing'
     and lease_token = p_lease_token
  returning true;
$$;

create or replace function public.learning_worker_fail_storage_deletion(
  p_outbox_id uuid,
  p_lease_token uuid,
  p_error_code text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  target_job_id uuid;
  new_retry_count integer;
begin
  if p_error_code <> 'storage_delete_failed' then
    raise exception 'invalid_error_code' using errcode = 'check_violation';
  end if;
  update public.storage_deletion_outbox
     set status = 'failed',
         retry_count = least(retry_count + 1, 20),
         lease_token = null,
         leased_until = null,
         next_attempt_at = now() + make_interval(
           secs => least(300, (5 * power(2, least(retry_count, 6)))::integer)
         ),
         last_error_code = p_error_code,
         updated_at = now()
   where id = p_outbox_id
     and status = 'processing'
     and lease_token = p_lease_token
  returning deletion_job_id, retry_count into target_job_id, new_retry_count;
  if target_job_id is null then
    return false;
  end if;
  update public.course_deletion_jobs
     set retry_count = least(retry_count + 1, 20),
         error_code = p_error_code,
         status = case when new_retry_count >= 20 then 'failed' else 'processing' end,
         completed_at = case when new_retry_count >= 20 then now() else null end
   where id = target_job_id;
  return true;
end;
$$;

create or replace function public.learning_worker_claim_expired_export()
returns table(export_id uuid, storage_key text, lease_token uuid)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  selected_id uuid;
  selected_key text;
  selected_token uuid;
begin
  select e.id, e.storage_key into selected_id, selected_key
    from public.learning_export_jobs e
   where e.expires_at <= now()
     and e.status <> 'expired'
     and e.cleanup_retry_count < 20
     and e.cleanup_next_attempt_at <= now()
     and (e.cleanup_lease_token is null or e.cleanup_leased_until <= now())
   order by e.expires_at, e.id
   for update skip locked
   limit 1;
  if selected_id is null then
    return;
  end if;
  selected_token := gen_random_uuid();
  update public.learning_export_jobs
     set cleanup_lease_token = selected_token,
         cleanup_leased_until = now() + interval '90 seconds'
   where id = selected_id;
  export_id := selected_id;
  storage_key := selected_key;
  lease_token := selected_token;
  return next;
end;
$$;

create or replace function public.learning_worker_complete_expired_export(
  p_export_id uuid,
  p_lease_token uuid
)
returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $$
  update public.learning_export_jobs
     set status = 'expired', storage_key = null, size_bytes = null,
         cleanup_lease_token = null, cleanup_leased_until = null,
         cleanup_last_error_code = null
   where id = p_export_id and cleanup_lease_token = p_lease_token
  returning true;
$$;

create or replace function public.learning_worker_fail_expired_export(
  p_export_id uuid,
  p_lease_token uuid,
  p_error_code text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if p_error_code <> 'storage_delete_failed' then
    raise exception 'invalid_error_code' using errcode = 'check_violation';
  end if;
  update public.learning_export_jobs
     set cleanup_retry_count = least(cleanup_retry_count + 1, 20),
         cleanup_lease_token = null,
         cleanup_leased_until = null,
         cleanup_next_attempt_at = now() + make_interval(
           secs => least(300, (5 * power(2, least(cleanup_retry_count, 6)))::integer)
         ),
         cleanup_last_error_code = p_error_code
   where id = p_export_id and cleanup_lease_token = p_lease_token;
  return found;
end;
$$;

create or replace function public.learning_worker_health_probe()
returns table(check_name text, status text, detail text)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  visible_jobs bigint;
  lifecycle_ready boolean;
begin
  select count(*) into visible_jobs
    from public.learning_submission_jobs jobs
   where jobs.status = 'queued' and jobs.visible_at <= now();
  check_name := 'queue_visibility';
  status := 'ok';
  detail := 'visible_jobs=' || visible_jobs;
  return next;

  lifecycle_ready :=
    has_function_privilege(session_user, 'public.learning_worker_claim_course_deletion()', 'EXECUTE')
    and has_function_privilege(session_user, 'public.learning_worker_claim_expired_export()', 'EXECUTE');
  check_name := 'lifecycle_commands';
  status := case when lifecycle_ready then 'ok' else 'failed' end;
  detail := case when lifecycle_ready then null else 'execute_privilege_missing' end;
  return next;
end;
$$;

revoke all on function public.queue_course_deletion_owned(uuid, text, text, boolean) from public;
grant execute on function public.queue_course_deletion_owned(uuid, text, text, boolean) to gustav_limited;

revoke all on function public.finalize_course_deletion(uuid) from public, gustav_worker;
revoke all on function public.learning_worker_claim_course_deletion() from public;
revoke all on function public.learning_worker_complete_storage_deletion(uuid, uuid) from public;
revoke all on function public.learning_worker_fail_storage_deletion(uuid, uuid, text) from public;
revoke all on function public.learning_worker_claim_expired_export() from public;
revoke all on function public.learning_worker_complete_expired_export(uuid, uuid) from public;
revoke all on function public.learning_worker_fail_expired_export(uuid, uuid, text) from public;
grant execute on function public.learning_worker_claim_course_deletion() to gustav_worker;
grant execute on function public.learning_worker_complete_storage_deletion(uuid, uuid) to gustav_worker;
grant execute on function public.learning_worker_fail_storage_deletion(uuid, uuid, text) to gustav_worker;
grant execute on function public.learning_worker_claim_expired_export() to gustav_worker;
grant execute on function public.learning_worker_complete_expired_export(uuid, uuid) to gustav_worker;
grant execute on function public.learning_worker_fail_expired_export(uuid, uuid, text) to gustav_worker;

revoke select, update on public.course_deletion_jobs from gustav_worker;
revoke select, update on public.storage_deletion_outbox from gustav_worker;
revoke select, update on public.learning_export_jobs from gustav_worker;

revoke all on function public.learning_worker_health_probe() from public;
grant execute on function public.learning_worker_health_probe() to gustav_web, gustav_operator, gustav_limited, gustav_worker;
