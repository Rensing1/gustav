-- Fix RLS recursion for modular access check.
--
-- Why:
--   `student_can_access_section(...)` is used by RLS policies on unit_sections,
--   unit_tasks and unit_materials. The modular extension must NOT query
--   `public.unit_sections`, otherwise we trigger infinite policy recursion.
--
-- Strategy:
--   Use `public.unit_modules` (Option B) as the authoritative mapping from
--   section_id -> unit_id and check unit_type + course membership there.

set check_function_bodies = off;

create or replace function public.student_can_access_section(
  p_student_sub text,
  p_section_id uuid
)
returns boolean
language sql
security invoker
set search_path = public, pg_temp
as $$
  with ctx as (
    select case
      when coalesce(current_setting('app.current_course_id', true), '') ~* '^[0-9a-f-]{36}$'
        then current_setting('app.current_course_id', true)::uuid
      else null
    end as course_id
  )
  select
    -- Linear: released section in the course.
    exists (
      select 1
        from public.module_section_releases r
        join public.course_modules m on m.id = r.course_module_id
        join public.course_memberships cm on cm.course_id = m.course_id
       where r.section_id = p_section_id
         and cm.student_id = p_student_sub
         and coalesce(r.visible, false) = true
    )
    or
    -- Modular: section_id must be mapped as a module AND the unit must be
    -- attached to the *current* course (course-scoped).
    exists (
      select 1
        from public.unit_modules um
        join public.units u on u.id = um.unit_id
        join public.course_modules m on m.unit_id = um.unit_id
        join public.course_memberships cm on cm.course_id = m.course_id
        join ctx on true
       where um.section_id = p_section_id
         and u.unit_type = 'modular'
         and cm.student_id = p_student_sub
         and m.course_id = ctx.course_id
    );
$$;

set check_function_bodies = on;
