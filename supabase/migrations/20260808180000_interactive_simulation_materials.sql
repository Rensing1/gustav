-- Teaching/Learning: self-contained interactive simulations as materials.

begin;

alter table public.unit_materials
  drop constraint if exists unit_materials_kind_check;

alter table public.unit_materials
  add constraint unit_materials_kind_check
  check (kind in ('markdown', 'file', 'simulation'));

alter table public.unit_materials
  drop constraint if exists unit_materials_file_fields_check;

alter table public.unit_materials
  add constraint unit_materials_file_fields_check
  check (
    case
      when kind = 'markdown' then
        storage_key is null
        and filename_original is null
        and mime_type is null
        and size_bytes is null
        and sha256 is null
      when kind = 'file' then
        storage_key is not null
        and filename_original is not null
        and mime_type is not null
        and size_bytes is not null
        and size_bytes > 0
        and sha256 is not null
        and sha256 ~ '^[0-9a-f]{64}$'
      when kind = 'simulation' then
        storage_key is not null
        and filename_original is not null
        and lower(filename_original) like '%.html'
        and mime_type = 'text/html'
        and size_bytes between 1 and 5242880
        and sha256 is not null
        and sha256 ~ '^[0-9a-f]{64}$'
        and alt_text is null
      else false
    end
  );

alter table public.upload_intents
  add column if not exists material_kind text not null default 'file';

alter table public.upload_intents
  drop constraint if exists upload_intents_material_kind_check;

alter table public.upload_intents
  add constraint upload_intents_material_kind_check
  check (material_kind in ('file', 'simulation'));

-- Keep the bucket private and extend its existing MIME allowlist additively.
do $$
begin
  if exists (
    select 1
      from information_schema.columns
     where table_schema = 'storage'
       and table_name = 'buckets'
       and column_name = 'allowed_mime_types'
  ) then
    update storage.buckets
       set public = false,
           allowed_mime_types = (
             select array_agg(distinct allowed_mime order by allowed_mime)
               from unnest(
                 coalesce(allowed_mime_types, array[]::text[])
                 || array['application/pdf', 'image/png', 'image/jpeg', 'text/html']::text[]
               ) allowed_mime
           )
     where id = 'materials';
  end if;
end$$;

create or replace function public.get_material_asset_metadata_batch_for_student(
  p_student_sub text,
  p_course_id uuid,
  p_material_ids uuid[]
)
returns table (
  material_id uuid,
  section_id uuid,
  unit_id uuid,
  kind text,
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
      m.kind,
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
     and m.kind in ('file', 'simulation')
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
    select mu.unit_id, states.section_id
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
    c.kind,
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
  or (c.unit_type = 'modular' and ms.section_id is not null)
  order by c.material_id;
$$;

revoke all on function public.get_material_asset_metadata_batch_for_student(text, uuid, uuid[]) from public;
grant execute on function public.get_material_asset_metadata_batch_for_student(text, uuid, uuid[]) to gustav_limited;

commit;
