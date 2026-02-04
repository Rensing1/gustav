-- Learning units: add unit_type (linear vs modular) and expose it to students.
--
-- Why:
--   The Learning UI needs to branch between the existing linear unit flow
--   (teacher section releases) and the upcoming modular unit flow (graph-based
--   unlock). For contract-first development we must expose `unit_type` in the
--   student unit listing and in teaching unit objects.
--
-- Notes:
--   - Default stays `linear` for all existing rows.
--   - The modular graph schema (phases/edges) is introduced in later migrations.

alter table public.units
  add column if not exists unit_type text not null default 'linear';

alter table public.units
  drop constraint if exists units_unit_type_check;

alter table public.units
  add constraint units_unit_type_check check (unit_type in ('linear', 'modular'));

-- ---------------------------------------------------------------------------
-- Learning helper: include unit_type in course units listing
-- ---------------------------------------------------------------------------

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
  unit_type text,
  module_position integer
)
language sql
security invoker
set search_path = public, pg_temp
as $$
  select u.id,
         u.title,
         u.summary,
         u.unit_type,
         m.position as module_position
    from public.course_memberships cm
    join public.course_modules m on m.course_id = cm.course_id
    join public.units u on u.id = m.unit_id
   where cm.course_id = p_course_id
     and cm.student_id = p_student_sub
   order by m.position asc, u.id asc;
$$;

-- SECURITY: functions are invoked by the backend role only; do not leave them executable
-- by PUBLIC (Postgres default when creating a function).
revoke all on function public.get_course_units_for_student(text, uuid) from public;
grant execute on function public.get_course_units_for_student(text, uuid) to gustav_limited;

set check_function_bodies = on;
