-- SECURITY: Harden teacher latest-submission helper (`get_latest_submission_for_owner`)
--
-- Why:
--   The teacher "Live" detail view uses `public.get_latest_submission_for_owner(...)`
--   to read the student's latest submission under RLS. Because this function is
--   SECURITY DEFINER, it must be hardened to reduce attack surface:
--     - PUBLIC must not be able to EXECUTE it
--     - search_path must not include attacker-controlled schemas (no pg_temp)
--     - authorization must bind to the session (`app.current_sub`), not to the
--       user-controlled parameter `p_owner_sub`
--
-- Notes:
--   We keep the `p_owner_sub` parameter for signature stability, but do not
--   trust it for authorization.
--
-- Local = Prod: apply via `supabase migration up`.

set check_function_bodies = off;

create or replace function public.get_latest_submission_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_task_id uuid,
  p_student_sub text
)
returns table (
  id uuid,
  task_id uuid,
  student_sub text,
  created_at timestamptz,
  completed_at timestamptz,
  kind text,
  score_raw integer,
  score_max integer,
  text_body text,
  mime_type text,
  size_bytes integer,
  storage_key text,
  feedback_md text,
  analysis_json jsonb
)
language sql
security definer
set search_path = pg_catalog, public
as $$
  with owner as (
    select 1
      from public.courses c
     where c.id = p_course_id
       and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
  ), relation as (
    select 1
      from public.unit_tasks t
      join public.unit_sections s on s.id = t.section_id
      join public.course_modules m on m.unit_id = s.unit_id and m.course_id = p_course_id
     where s.unit_id = p_unit_id
       and t.id = p_task_id
  ), member as (
    select 1
      from public.course_memberships cm
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
  ), latest as (
    select ls.id,
           ls.task_id,
           ls.student_sub,
           ls.created_at,
           ls.completed_at,
           ls.kind::text,
           ls.score_raw,
           ls.score_max,
           ls.text_body,
           ls.mime_type,
           ls.size_bytes,
           ls.storage_key,
           ls.feedback_md,
           ls.analysis_json
      from public.learning_submissions ls
     where ls.course_id = p_course_id
       and ls.task_id = p_task_id
       and ls.student_sub = p_student_sub
     order by ls.created_at desc
     limit 1
  )
  select l.id,
         l.task_id,
         l.student_sub,
         l.created_at,
         l.completed_at,
         l.kind,
         l.score_raw,
         l.score_max,
         l.text_body,
         l.mime_type,
         l.size_bytes,
         l.storage_key,
         l.feedback_md,
         l.analysis_json
    from owner, relation, member, latest l;
$$;

revoke all on function public.get_latest_submission_for_owner(text, uuid, uuid, uuid, text) from public;
grant execute on function public.get_latest_submission_for_owner(text, uuid, uuid, uuid, text) to gustav_limited;

set check_function_bodies = on;

