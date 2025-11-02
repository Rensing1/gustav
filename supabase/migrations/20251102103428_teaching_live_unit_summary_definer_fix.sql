-- Adjust helper to SECURITY DEFINER and grant execute to gustav_limited.

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
  completed_at_iso text
)
language sql
security definer
set search_path = public, pg_temp
as $$
  with owner as (
    select 1 from public.courses c where c.id = p_course_id and c.teacher_id = p_owner_sub
  ), tasks_in_unit as (
    select t.id as task_id
      from public.unit_tasks t
      join public.unit_sections s on s.id = t.section_id
      join public.course_modules m on m.unit_id = s.unit_id and m.course_id = p_course_id
     where s.unit_id = p_unit_id
  ), latest as (
    select distinct on (ls.student_sub, ls.task_id)
           ls.student_sub,
           ls.task_id,
           ls.id as submission_id,
           ls.created_at,
           ls.completed_at
      from public.learning_submissions ls
      join tasks_in_unit tiu on tiu.task_id = ls.task_id
     where ls.course_id = p_course_id
       and (p_updated_since is null or greatest(ls.created_at, coalesce(ls.completed_at, ls.created_at)) > p_updated_since)
     order by ls.student_sub, ls.task_id, ls.created_at desc
  )
  select l.student_sub,
         l.task_id,
         l.submission_id,
         to_char(l.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as created_at_iso,
         case when l.completed_at is null then null else to_char(l.completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') end as completed_at_iso
    from owner, latest l
   order by l.student_sub asc, l.task_id asc
   offset greatest(coalesce(p_offset,0),0)
   limit case when coalesce(p_limit,0) < 1 then 100 when p_limit > 200 then 200 else p_limit end;
$$;

grant execute on function public.get_unit_latest_submissions_for_owner(text, uuid, uuid, timestamptz, integer, integer) to gustav_limited;

