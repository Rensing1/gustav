-- Learning helper functions — visibility guard + attempt numbering.

set check_function_bodies = off;

drop function if exists public.hash_course_task_student(uuid, uuid, text);
create or replace function public.hash_course_task_student(p_course_id uuid, p_task_id uuid, p_student_sub text)
returns bigint
language sql
immutable
strict
as $$
  select hashtextextended(
    coalesce(p_course_id::text, '') || ':' ||
    coalesce(p_task_id::text, '') || ':' ||
    coalesce(p_student_sub, ''),
    0
  );
$$;

drop function if exists public.next_attempt_nr(uuid, uuid, text);
create or replace function public.next_attempt_nr(p_course_id uuid, p_task_id uuid, p_student_sub text)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  next_nr integer;
begin
  perform pg_advisory_xact_lock(public.hash_course_task_student(p_course_id, p_task_id, p_student_sub));
  select coalesce(max(attempt_nr), 0) + 1
    into next_nr
    from public.learning_submissions
   where course_id = p_course_id
     and task_id = p_task_id
     and student_sub = p_student_sub;
  return next_nr;
end;
$$;

drop function if exists public.check_task_visible_to_student(text, uuid, uuid);
create or replace function public.check_task_visible_to_student(p_student_sub text, p_course_id uuid, p_task_id uuid)
returns boolean
language sql
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
      from public.course_memberships cm
      join public.unit_tasks t on t.id = p_task_id
      join public.unit_sections s on s.id = t.section_id
      join public.course_modules m on m.unit_id = t.unit_id and m.course_id = p_course_id
      join public.module_section_releases r on r.course_module_id = m.id and r.section_id = s.id
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
       and coalesce(r.visible, false) = true
  );
$$;

grant execute on function public.hash_course_task_student(uuid, uuid, text) to gustav_limited;
grant execute on function public.next_attempt_nr(uuid, uuid, text) to gustav_limited;
grant execute on function public.check_task_visible_to_student(text, uuid, uuid) to gustav_limited;

drop function if exists public.get_released_sections_for_student(text, uuid, integer, integer);
create or replace function public.get_released_sections_for_student(
  p_student_sub text,
  p_course_id uuid,
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
  join public.unit_sections s on s.id = r.section_id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and coalesce(r.visible, false) = true
  order by s.position, s.id
  offset greatest(coalesce(p_offset, 0), 0)
  limit case
          when coalesce(p_limit, 0) < 1 then 50
          when p_limit > 100 then 100
          else p_limit
        end;
$$;

drop function if exists public.get_released_materials_for_student(text, uuid, uuid);
create or replace function public.get_released_materials_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_section_id uuid
)
returns table (
  id uuid,
  title text,
  kind text,
  body_md text,
  mime_type text,
  size_bytes integer,
  filename_original text,
  storage_key text,
  sha256 text,
  alt_text text,
  material_position integer,
  created_at_iso text,
  updated_at_iso text
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select
    m.id,
    m.title,
    m.kind,
    m.body_md,
    m.mime_type,
    m.size_bytes,
    m.filename_original,
    m.storage_key,
    m.sha256,
    m.alt_text,
    m.position as material_position,
    to_char(m.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
    to_char(m.updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
  from public.course_memberships cm
  join public.course_modules mod on mod.course_id = cm.course_id
  join public.module_section_releases r on r.course_module_id = mod.id and r.section_id = p_section_id
  join public.unit_sections s on s.id = p_section_id and s.unit_id = mod.unit_id
  join public.unit_materials m on m.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
    and coalesce(r.visible, false) = true
  order by m.position, m.id;
$$;

drop function if exists public.get_released_tasks_for_student(text, uuid, uuid);
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
  join public.module_section_releases r on r.course_module_id = mod.id
                                  and r.section_id = p_section_id
                                  and coalesce(r.visible, false) = true
  join public.unit_sections s on s.id = p_section_id and s.unit_id = mod.unit_id
  join public.unit_tasks t on t.section_id = s.id
  where cm.course_id = p_course_id
    and cm.student_id = p_student_sub
  order by t.position, t.id;
$$;

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
  max_attempts integer
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select
    t.id,
    t.section_id,
    t.unit_id,
    t.max_attempts
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

grant execute on function public.get_released_sections_for_student(text, uuid, integer, integer) to gustav_limited;
grant execute on function public.get_released_materials_for_student(text, uuid, uuid) to gustav_limited;
grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;
grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
