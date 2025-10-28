-- Learning: extend get_task_metadata_for_student to expose rubric criteria for students.

set check_function_bodies = off;

drop function if exists public.get_task_metadata_for_student(text, uuid, uuid);

create or replace function public.get_task_metadata_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_task_id uuid
)
returns table (
  task_id uuid,
  section_id uuid,
  unit_id uuid,
  max_attempts integer,
  criteria text[]
)
language sql
security definer
set search_path = pg_catalog, public
as $$
  select
    t.id,
    t.section_id,
    t.unit_id,
    t.max_attempts,
    t.criteria
  from public.course_memberships cm
  join public.course_modules mod on mod.course_id = cm.course_id
  join public.unit_sections s on s.unit_id = mod.unit_id
  join public.unit_tasks t on t.section_id = s.id
  join public.module_section_releases r on r.course_module_id = mod.id
                                  and r.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and t.id = p_task_id
    and coalesce(r.visible, false) = true
  limit 1;
$$;

do $$
begin
  begin
    alter function public.get_task_metadata_for_student(text, uuid, uuid)
      owner to gustav_limited;
  exception when insufficient_privilege then
    raise notice 'Skipping owner change for get_task_metadata_for_student: insufficient privileges';
  end;
  begin
    grant execute on function public.get_task_metadata_for_student(text, uuid, uuid)
      to gustav_limited;
  exception when others then
    raise notice 'Grant execute failed for get_task_metadata_for_student: %', sqlerrm;
  end;
end $$;

set check_function_bodies = on;
