-- Learning — Helper to list released sections for a unit (student scope)

set check_function_bodies = off;

drop function if exists public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer);
create or replace function public.get_released_sections_for_student_by_unit(
  p_student_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_limit integer,
  p_offset integer
)
returns table (
  section_id uuid,
  section_title text,
  section_position integer,
  unit_id uuid,
  course_module_id uuid
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select
    s.id,
    s.title,
    s.position,
    s.unit_id,
    m.id
  from public.course_memberships cm
  join public.course_modules m on m.course_id = cm.course_id
  join public.module_section_releases r on r.course_module_id = m.id
  join public.unit_sections s on s.id = r.section_id and s.unit_id = m.unit_id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and m.unit_id = p_unit_id
    and coalesce(r.visible, false) = true
  order by s.position, s.id
  offset greatest(coalesce(p_offset, 0), 0)
  limit case
          when coalesce(p_limit, 0) < 1 then 50
          when p_limit > 100 then 100
          else p_limit
        end;
$$;

-- Ensure SECURITY DEFINER function ownership is set to the limited role
alter function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)
  owner to gustav_limited;
grant execute on function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)
  to gustav_limited;
