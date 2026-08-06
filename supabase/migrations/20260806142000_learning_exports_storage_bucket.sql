-- Keep generated learning archives separate from learner submission files.

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'storage'
      and table_name = 'buckets'
      and column_name = 'allowed_mime_types'
  ) then
    update storage.buckets
       set public = false,
           allowed_mime_types = array['application/zip']::text[]
     where id = 'learning-exports';
  end if;
end $$;

create or replace function public.queue_course_deletion_owned(
  p_course_id uuid, p_owner_sub text, p_confirmation_title text, p_confirm_student_data_loss boolean
)
returns public.course_deletion_jobs language plpgsql security definer
set search_path = pg_catalog, public as $$
declare course_row public.courses; impact_row jsonb; result public.course_deletion_jobs;
begin
  select * into course_row from public.courses
   where id = p_course_id and teacher_id = p_owner_sub and status <> 'deleting' for update;
  if not found then raise exception 'course_not_found' using errcode = 'no_data_found'; end if;
  if not p_confirm_student_data_loss or p_confirmation_title <> course_row.title then
    raise exception 'deletion_confirmation_mismatch' using errcode = 'check_violation';
  end if;
  impact_row := public.course_deletion_impact_owned(p_course_id, p_owner_sub);
  insert into public.course_deletion_jobs(course_id, owner_sub, course_title, impact)
  values (p_course_id, p_owner_sub, course_row.title, impact_row) returning * into result;
  insert into public.storage_deletion_outbox(deletion_job_id, bucket, storage_key)
  select result.id, 'submissions', s.storage_key from public.learning_submissions s
   where s.course_id = p_course_id and s.storage_key is not null on conflict do nothing;
  insert into public.storage_deletion_outbox(deletion_job_id, bucket, storage_key)
  select result.id, 'learning-exports', e.storage_key from public.learning_export_jobs e
   where e.course_id = p_course_id and e.storage_key is not null on conflict do nothing;
  update public.courses set status = 'deleting' where id = p_course_id;
  return result;
end;
$$;
