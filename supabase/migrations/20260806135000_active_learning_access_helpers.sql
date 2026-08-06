-- Resolve active learning access in one privileged, indexed lookup per policy.
-- Former members retain their portfolio through dedicated archive helpers, but
-- they must not regain ordinary course materials through legacy RLS helpers.

create or replace function public.student_is_course_member(
  p_student_sub text,
  p_course_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1
      from public.course_memberships cm
      join public.courses c on c.id = cm.course_id
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
       and cm.ended_at is null
       and c.status = 'active'
  );
$$;

create or replace function public.student_can_access_unit(
  p_student_sub text,
  p_unit_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      join public.course_memberships cm on cm.course_id = m.course_id
     where m.unit_id = p_unit_id
       and cm.student_id = p_student_sub
       and cm.ended_at is null
       and c.status = 'active'
  );
$$;

create or replace function public.student_can_access_course_module(
  p_student_sub text,
  p_course_module_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      join public.course_memberships cm on cm.course_id = m.course_id
     where m.id = p_course_module_id
       and cm.student_id = p_student_sub
       and cm.ended_at is null
       and c.status = 'active'
  );
$$;

create or replace function public.student_can_access_section(
  p_student_sub text,
  p_section_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  with ctx as (
    select case
      when coalesce(current_setting('app.current_course_id', true), '') ~* '^[0-9a-f-]{36}$'
        then current_setting('app.current_course_id', true)::uuid
      else null
    end as course_id
  )
  select exists (
    select 1
      from public.module_section_releases r
      join public.course_modules m on m.id = r.course_module_id
      join public.courses c on c.id = m.course_id
      join public.course_memberships cm on cm.course_id = m.course_id
     where r.section_id = p_section_id
       and cm.student_id = p_student_sub
       and cm.ended_at is null
       and c.status = 'active'
       and coalesce(r.visible, false) = true
  ) or exists (
    select 1
      from public.unit_modules um
      join public.units u on u.id = um.unit_id
      join public.course_modules m on m.unit_id = um.unit_id
      join public.courses c on c.id = m.course_id
      join public.course_memberships cm on cm.course_id = m.course_id
      join ctx on true
     where um.section_id = p_section_id
       and u.unit_type = 'modular'
       and cm.student_id = p_student_sub
       and cm.ended_at is null
       and c.status = 'active'
       and m.course_id = ctx.course_id
  );
$$;

revoke all on function public.student_is_course_member(text, uuid) from public;
revoke all on function public.student_can_access_unit(text, uuid) from public;
revoke all on function public.student_can_access_course_module(text, uuid) from public;
revoke all on function public.student_can_access_section(text, uuid) from public;
grant execute on function public.student_is_course_member(text, uuid) to gustav_limited;
grant execute on function public.student_can_access_unit(text, uuid) to gustav_limited;
grant execute on function public.student_can_access_course_module(text, uuid) to gustav_limited;
grant execute on function public.student_can_access_section(text, uuid) to gustav_limited;

-- The archive snapshot must use the historical release-table column name.
create or replace function public.archive_course_owned(p_course_id uuid, p_owner_sub text)
returns public.courses
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  result public.courses;
begin
  select * into result from public.courses where id = p_course_id and teacher_id = p_owner_sub for update;
  if not found then raise exception 'course_not_found' using errcode = 'no_data_found'; end if;
  if result.status <> 'active' then raise exception 'course_not_active' using errcode = 'object_not_in_prerequisite_state'; end if;
  if not public.course_metadata_complete(p_course_id) then
    raise exception 'course_metadata_incomplete' using errcode = 'check_violation';
  end if;

  insert into public.course_archive_snapshots(course_id, snapshot)
  values (p_course_id, jsonb_build_object(
    'version', 1,
    'archived_at', now(),
    'course', to_jsonb(result),
    'modules', coalesce((select jsonb_agg(to_jsonb(cm) order by cm.position) from public.course_modules cm where cm.course_id = p_course_id), '[]'::jsonb),
    'releases', coalesce((select jsonb_agg(to_jsonb(r)) from public.module_section_releases r join public.course_modules cm on cm.id = r.course_module_id where cm.course_id = p_course_id), '[]'::jsonb)
  ))
  on conflict (course_id) do update set snapshot = excluded.snapshot, created_at = now();

  update public.learning_dialog_sessions
     set status = 'abandoned', abandoned_at = now(), updated_at = now()
   where course_id = p_course_id and status = 'active';

  update public.courses
     set status = 'archived', archived_at = now(), archived_by = p_owner_sub
   where id = p_course_id
  returning * into result;
  return result;
end;
$$;
