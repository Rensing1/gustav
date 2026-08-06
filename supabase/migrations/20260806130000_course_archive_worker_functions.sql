-- Least-privilege worker helpers for learning exports and course deletion.

create or replace function public.learning_worker_claim_export()
returns public.learning_export_jobs language plpgsql security definer
set search_path = pg_catalog, public as $$
declare result public.learning_export_jobs;
begin
  update public.learning_export_jobs
     set status = 'generating', started_at = now(), retry_count = retry_count + 1
   where id = (select id from public.learning_export_jobs
                where status = 'pending' and expires_at > now()
                order by requested_at, id for update skip locked limit 1)
  returning * into result;
  return result;
end;
$$;

create or replace function public.learning_worker_export_snapshot(p_job_id uuid)
returns jsonb language sql stable security definer
set search_path = pg_catalog, public as $$
  select jsonb_build_object(
    'course', jsonb_build_object(
      'id', c.id, 'title', c.title, 'subject', c.subject,
      'grade_level', c.grade_level, 'school_year_start', c.school_year_start
    ),
    'cutoff_at', e.cutoff_at,
    'submissions', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', s.id, 'kind', s.kind, 'created_at', s.created_at,
        'completed_at', s.completed_at, 'text_body', s.text_body,
        'feedback_md', s.feedback_md, 'analysis_json', s.analysis_json,
        'storage_key', s.storage_key, 'mime_type', s.mime_type,
        'task_snapshot', snap.task_snapshot,
        'dialog', case when s.dialog_session_id is null then null else (
          select jsonb_build_object(
            'closing_response', ds.closing_answer_md,
            'turns', coalesce(jsonb_agg(jsonb_build_object(
              'student_message', dt.student_message_md,
              'assistant_message', dt.assistant_reply_md,
              'starter_used', dt.used_sentence_starter_md
            ) order by dt.round_nr) filter (where dt.id is not null), '[]'::jsonb)
          )
          from public.learning_dialog_sessions ds
          left join public.learning_dialog_turns dt on dt.session_id = ds.id
          where ds.id = s.dialog_session_id group by ds.id
        ) end
      ) order by s.created_at, s.id)
      from public.learning_submissions s
      join public.learning_submission_task_snapshots snap on snap.submission_id = s.id
      where s.course_id = e.course_id and s.student_sub = e.student_sub
        and s.created_at <= e.cutoff_at
        and (s.intent = 'submit' or s.feedback_md is not null)
    ), '[]'::jsonb)
  )
  from public.learning_export_jobs e join public.courses c on c.id = e.course_id
  where e.id = p_job_id and e.status = 'generating';
$$;

create or replace function public.learning_worker_complete_export(p_job_id uuid, p_storage_key text, p_size_bytes bigint)
returns boolean language sql security definer set search_path = pg_catalog, public as $$
  update public.learning_export_jobs
     set status = 'ready', storage_key = p_storage_key, size_bytes = p_size_bytes,
         completed_at = now(), error_code = null
   where id = p_job_id and status = 'generating' and expires_at > now()
  returning true;
$$;

create or replace function public.learning_worker_fail_export(p_job_id uuid, p_error_code text)
returns boolean language sql security definer set search_path = pg_catalog, public as $$
  update public.learning_export_jobs
     set status = 'failed', completed_at = now(), error_code = left(p_error_code, 80)
   where id = p_job_id and status in ('pending', 'generating') returning true;
$$;

revoke all on function public.learning_worker_claim_export() from public;
revoke all on function public.learning_worker_export_snapshot(uuid) from public;
revoke all on function public.learning_worker_complete_export(uuid, text, bigint) from public;
revoke all on function public.learning_worker_fail_export(uuid, text) from public;
grant execute on function public.learning_worker_claim_export() to gustav_worker;
grant execute on function public.learning_worker_export_snapshot(uuid) to gustav_worker;
grant execute on function public.learning_worker_complete_export(uuid, text, bigint) to gustav_worker;
grant execute on function public.learning_worker_fail_export(uuid, text) to gustav_worker;

-- Exports share the existing private submissions bucket.
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
  select result.id, 'submissions', e.storage_key from public.learning_export_jobs e
   where e.course_id = p_course_id and e.storage_key is not null on conflict do nothing;
  update public.courses set status = 'deleting' where id = p_course_id;
  return result;
end;
$$;
