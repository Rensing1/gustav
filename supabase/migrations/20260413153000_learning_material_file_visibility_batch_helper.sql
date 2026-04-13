-- Learning: set-based student file-material visibility helper.
--
-- Why:
--   The first material visibility helper unified behavior, but the Python
--   batch path still called a single-material SQL helper once per file. This
--   follow-up migration keeps the logic inside the learning context while
--   resolving modular unlock states once per affected unit.

set check_function_bodies = off;

create or replace function public.get_material_file_metadata_batch_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_material_ids uuid[]
)
returns table (
  material_id uuid,
  section_id uuid,
  unit_id uuid,
  mime_type text,
  size_bytes integer,
  storage_key text,
  filename_original text
)
language sql
security invoker
set search_path = pg_catalog, public
as $$
  with _ctx as (
    select set_config('app.current_course_id', p_course_id::text, true) as _
  ),
  requested as (
    select distinct requested.material_id
      from _ctx
      join unnest(coalesce(p_material_ids, array[]::uuid[])) as requested(material_id) on true
  ),
  candidate as (
    select
      m.id as material_id,
      m.section_id,
      m.unit_id,
      m.mime_type,
      m.size_bytes,
      m.storage_key,
      m.filename_original,
      u.unit_type,
      cm.id as course_module_id
    from requested
    join public.course_memberships mem
      on mem.course_id = p_course_id
     and mem.student_id = p_student_sub
    join public.unit_materials m
      on m.id = requested.material_id
     and m.kind = 'file'
    join public.units u
      on u.id = m.unit_id
    join public.course_modules cm
      on cm.course_id = p_course_id
     and cm.unit_id = m.unit_id
  ),
  modular_units as (
    select distinct c.unit_id
      from candidate c
     where c.unit_type = 'modular'
  ),
  modular_states as (
    select
      mu.unit_id,
      states.section_id
    from modular_units mu
    join lateral public.get_modular_unit_module_states_for_student(
          p_student_sub,
          p_course_id,
          mu.unit_id
    ) states on true
    where states.status in ('open', 'done')
  )
  select
    c.material_id,
    c.section_id,
    c.unit_id,
    c.mime_type,
    c.size_bytes,
    c.storage_key,
    c.filename_original
  from candidate c
  left join modular_states ms
    on ms.unit_id = c.unit_id
   and ms.section_id = c.section_id
  where (
    c.unit_type = 'linear'
    and exists (
      select 1
        from public.module_section_releases r
       where r.course_module_id = c.course_module_id
         and r.section_id = c.section_id
         and coalesce(r.visible, false) = true
    )
  )
  or (
    c.unit_type = 'modular'
    and ms.section_id is not null
  )
  order by c.material_id;
$$;

create or replace function public.get_material_file_metadata_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_material_id uuid
)
returns table (
  material_id uuid,
  section_id uuid,
  unit_id uuid,
  mime_type text,
  size_bytes integer,
  storage_key text,
  filename_original text
)
language sql
security invoker
set search_path = pg_catalog, public
as $$
  select *
    from public.get_material_file_metadata_batch_for_student(
      p_student_sub,
      p_course_id,
      array[p_material_id]::uuid[]
    )
   limit 1;
$$;

revoke all on function public.get_material_file_metadata_batch_for_student(text, uuid, uuid[]) from public;
grant execute on function public.get_material_file_metadata_batch_for_student(text, uuid, uuid[]) to gustav_limited;

revoke all on function public.get_material_file_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_material_file_metadata_for_student(text, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
