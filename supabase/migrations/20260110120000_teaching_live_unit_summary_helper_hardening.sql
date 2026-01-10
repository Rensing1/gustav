-- SECURITY: Harden teacher live-unit helper (`get_unit_latest_submissions_for_owner`)
--
-- Why:
--   This function is SECURITY DEFINER and reads from `learning_submissions`,
--   which is protected by student-scoped RLS. Teachers need aggregated
--   visibility for their own courses, but the helper must remain safe:
--     - PUBLIC must not be able to EXECUTE it
--     - search_path must not include attacker-controlled schemas (no pg_temp)
--     - ownership must bind to the session (`app.current_sub`), not a parameter
--
-- Notes:
--   We keep the `p_owner_sub` parameter for signature stability, but we do not
--   trust it for authorization. Authorization is derived from `app.current_sub`.

set check_function_bodies = off;

create or replace function public.get_unit_latest_submissions_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_updated_since timestamptz default null,
  p_limit integer default 100,
  p_offset integer default 0
)
returns table (
  student_sub text,
  task_id uuid,
  submission_id uuid,
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
           bool_or(ls.score_max > 0 and ls.score_raw = ls.score_max) as completed
      from public.learning_submissions ls
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
           ls.created_at,
           ls.completed_at,
           tiu.task_kind
      from public.learning_submissions ls
      join tasks_in_unit tiu on tiu.task_id = ls.task_id
     where ls.course_id = p_course_id
       and (p_updated_since is null
         or greatest(ls.created_at, coalesce(ls.completed_at, ls.created_at)) > p_updated_since)
     order by ls.student_sub, ls.task_id, ls.created_at desc
  )
  select l.student_sub,
         l.task_id,
         l.submission_id,
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
   order by l.student_sub asc, l.task_id asc
   offset greatest(coalesce(p_offset,0),0)
   limit case
     when coalesce(p_limit,0) < 1 then 100
     when p_limit > 200 then 200
     else p_limit
   end;
$$;

revoke all on function public.get_unit_latest_submissions_for_owner(text, uuid, uuid, timestamptz, integer, integer) from public;
grant execute on function public.get_unit_latest_submissions_for_owner(text, uuid, uuid, timestamptz, integer, integer) to gustav_limited;

set check_function_bodies = on;

