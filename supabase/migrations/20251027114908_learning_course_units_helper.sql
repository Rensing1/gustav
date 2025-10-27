-- Learning — Helper to list units for a student's course
-- SECURITY DEFINER with hardened search_path and fully-qualified table names

set check_function_bodies = off;

drop function if exists public.get_course_units_for_student(text, uuid);
create or replace function public.get_course_units_for_student(
  p_student_sub text,
  p_course_id uuid
)
returns table (
  unit_id uuid,
  title text,
  summary text,
  module_position integer
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select u.id, u.title, u.summary, m.position as module_position
    from public.course_memberships cm
    join public.course_modules m on m.course_id = cm.course_id
    join public.units u on u.id = m.unit_id
   where cm.course_id = p_course_id
     and cm.student_id = p_student_sub
   order by m.position asc, u.id asc;
$$;

-- Ensure the SECURITY DEFINER function is owned by the limited, non-BYPASSRLS role
alter function public.get_course_units_for_student(text, uuid) owner to gustav_limited;

grant execute on function public.get_course_units_for_student(text, uuid) to gustav_limited;

set check_function_bodies = on;
