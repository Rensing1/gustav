-- Teaching: fix latest-submission helper membership guard
--
-- Why:
--   The teacher "Live" detail view uses `public.get_latest_submission_for_owner(...)`
--   to read the student's latest submission under RLS. A previous revision could
--   reference a non-existent column (`course_memberships.student_sub`) instead of the
--   correct column (`course_memberships.student_id`). Because our migrations disable
--   function body checks, that bug can slip through migration-time validation and only
--   surface at runtime.
--
--   This migration redefines the function body (no signature change) so already-migrated
--   local databases are repaired via `supabase migration up` (Local = Prod).

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
set search_path = public, pg_temp
as $$
  with owner as (
    select 1 from public.courses c where c.id = p_course_id and c.teacher_id = p_owner_sub
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

grant execute on function public.get_latest_submission_for_owner(text, uuid, uuid, uuid, text) to gustav_limited;
