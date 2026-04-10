-- Teaching Live: bulk aggregates for the exact learner page in the summary view.
--
-- Why:
--   `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
--   paginates by learners, not by `(student_sub, task_id)` cells. The older
--   helper pages by cells, which truncates later learners when a unit has many
--   tasks. This helper accepts the explicit learner page and returns the latest
--   submission aggregate for each learner-task pair in one bulk call.

set check_function_bodies = off;

create or replace function public.get_unit_latest_submission_aggregates_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_student_subs text[]
)
returns table (
  student_sub text,
  task_id uuid,
  submission_id uuid,
  analysis_status text,
  analysis_json jsonb,
  score_raw integer,
  score_max integer,
  created_at_iso text,
  completed_at_iso text,
  h5p_completed boolean
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
  ), requested_students as (
    select distinct unnest(coalesce(p_student_subs, array[]::text[])) as student_sub
  ), member_students as (
    select rs.student_sub
      from requested_students rs
      join public.course_memberships cm
        on cm.course_id = p_course_id
       and cm.student_id = rs.student_sub
  ), tasks_in_unit as (
    select t.id as task_id,
           t.kind as task_kind
      from public.unit_tasks t
      join public.unit_sections s on s.id = t.section_id
      join public.course_modules m
        on m.unit_id = s.unit_id
       and m.course_id = p_course_id
     where s.unit_id = p_unit_id
  ), h5p_done as (
    select ls.student_sub,
           ls.task_id,
           bool_or(ls.score_raw = ls.score_max) as completed
      from public.learning_submissions ls
      join member_students ms on ms.student_sub = ls.student_sub
      join tasks_in_unit tiu on tiu.task_id = ls.task_id
     where ls.course_id = p_course_id
       and tiu.task_kind = 'h5p'
       and ls.kind = 'h5p'
     group by ls.student_sub, ls.task_id
  ), latest as (
    select distinct on (ls.student_sub, ls.task_id)
           ls.student_sub,
           ls.task_id,
           ls.id as submission_id,
           ls.analysis_status::text,
           ls.analysis_json,
           ls.score_raw,
           ls.score_max,
           ls.created_at,
           ls.completed_at,
           tiu.task_kind
      from public.learning_submissions ls
      join member_students ms on ms.student_sub = ls.student_sub
      join tasks_in_unit tiu on tiu.task_id = ls.task_id
     where ls.course_id = p_course_id
     order by ls.student_sub, ls.task_id, ls.created_at desc, ls.attempt_nr desc, ls.id desc
  )
  select l.student_sub,
         l.task_id,
         l.submission_id,
         l.analysis_status,
         l.analysis_json,
         l.score_raw,
         l.score_max,
         to_char(l.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as created_at_iso,
         case
           when l.completed_at is null then null
           else to_char(l.completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
         end as completed_at_iso,
         case
           when l.task_kind = 'h5p' then coalesce(h.completed, false)
           else null
         end as h5p_completed
    from owner,
         latest l
    left join h5p_done h
      on h.student_sub = l.student_sub
     and h.task_id = l.task_id
   order by l.student_sub asc, l.task_id asc;
$$;

revoke all on function public.get_unit_latest_submission_aggregates_for_owner(text, uuid, uuid, text[]) from public;
grant execute on function public.get_unit_latest_submission_aggregates_for_owner(text, uuid, uuid, text[]) to gustav_limited;

set check_function_bodies = on;
