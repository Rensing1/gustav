-- Learning: central student file-material visibility helper.
--
-- Why:
--   Student material lists, SSR previews, and the stable file-stream routes
--   must use one shared visibility decision for linear and modular units.
--
-- Result:
--   - new function: get_material_file_metadata_for_student(text, uuid, uuid)
--   - returns metadata only for visible `kind='file'` materials
--   - keeps `storage_key` server-internal while reusing one auth decision

set check_function_bodies = off;

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
  with _ctx as (
    select set_config('app.current_course_id', p_course_id::text, true) as _
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
    from _ctx
    join public.course_memberships mem
      on mem.course_id = p_course_id
     and mem.student_id = p_student_sub
    join public.unit_materials m
      on m.id = p_material_id
     and m.kind = 'file'
    join public.units u
      on u.id = m.unit_id
    join public.course_modules cm
      on cm.course_id = p_course_id
     and cm.unit_id = m.unit_id
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
    and public.modular_section_is_open_or_done_for_student(
      p_student_sub,
      p_course_id,
      c.unit_id,
      c.section_id
    )
  )
  limit 1;
$$;

revoke all on function public.get_material_file_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_material_file_metadata_for_student(text, uuid, uuid) to gustav_limited;

set check_function_bodies = on;
