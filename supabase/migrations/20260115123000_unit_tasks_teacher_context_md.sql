-- Migration: Rename unit task hints to teacher-only AI context
--
-- Why:
--   The previous column name `hints_md` suggested "hints for students". In
--   practice the field is used as private teacher-provided context for the AI
--   evaluation/feedback pipeline and must not be shown to students.
--
-- Goals:
--   1) Rename the persisted column on `public.unit_tasks` to `teacher_context_md`.
--   2) Remove the field from the student-scoped helper `get_released_tasks_for_student`
--      so the Learning API cannot accidentally expose it.

do $$
begin
  if exists (
    select 1
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'unit_tasks'
       and column_name = 'hints_md'
  ) and not exists (
    select 1
      from information_schema.columns
     where table_schema = 'public'
       and table_name = 'unit_tasks'
       and column_name = 'teacher_context_md'
  ) then
    execute 'alter table public.unit_tasks rename column hints_md to teacher_context_md';
  end if;
end $$;

-- NOTE: Postgres cannot change a RETURNS TABLE (OUT params) signature via
-- CREATE OR REPLACE. We must drop first, then recreate with the new columns.
drop function if exists public.get_released_tasks_for_student(text, uuid, uuid);
create function public.get_released_tasks_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_section_id uuid
)
returns table (
  id uuid,
  instruction_md text,
  criteria text[],
  due_at_iso text,
  max_attempts integer,
  kind text,
  h5p_content_id text,
  h5p_display_options jsonb,
  task_position integer,
  created_at_iso text,
  updated_at_iso text
)
language sql
security invoker
set search_path = public, pg_temp
as $$
  select
    t.id,
    t.instruction_md,
    t.criteria,
    case
      when t.due_at is null then null
      else to_char(t.due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    end,
    t.max_attempts,
    t.kind,
    t.h5p_content_id,
    t.h5p_display_options,
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

-- SECURITY: functions are invoked by the backend role only; do not leave them executable
-- by PUBLIC (Postgres default when creating a function).
revoke all on function public.get_released_tasks_for_student(text, uuid, uuid) from public;
grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;

-- Best-effort: keep ownership consistent (avoid BYPASSRLS owners).
do $$
begin
  if to_regprocedure('public.get_released_tasks_for_student(text, uuid, uuid)') is not null then
    begin
      alter function public.get_released_tasks_for_student(text, uuid, uuid) owner to gustav_limited;
    exception when insufficient_privilege then
      raise notice 'Skipping owner change for get_released_tasks_for_student: insufficient privileges';
    end;
  end if;
end $$;
