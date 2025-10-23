-- Learning RLS hardening — ensure unreleased tasks never leak to students.

set check_function_bodies = off;

create or replace function public.get_released_tasks_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_section_id uuid
)
returns table (
  id uuid,
  instruction_md text,
  criteria text[],
  hints_md text,
  due_at_iso text,
  max_attempts integer,
  task_position integer,
  created_at_iso text,
  updated_at_iso text
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select
    t.id,
    t.instruction_md,
    t.criteria,
    t.hints_md,
    case
      when t.due_at is null then null
      else to_char(t.due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    end,
    t.max_attempts,
    t.position as task_position,
    to_char(t.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(t.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
  from public.course_memberships cm
  join public.course_modules mod on mod.course_id = cm.course_id
  join public.module_section_releases r
    on r.course_module_id = mod.id
   and r.section_id = p_section_id
   and coalesce(r.visible, false) = true
  join public.unit_sections s on s.id = p_section_id and s.unit_id = mod.unit_id
  join public.unit_tasks t on t.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
  order by t.position, t.id;
$$;

grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
