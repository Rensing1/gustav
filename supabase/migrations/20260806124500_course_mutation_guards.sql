-- Keep course-specific authoring mutations behind one database lifecycle guard.

create or replace function public.guard_course_mutation()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare target_course_id uuid;
declare target_status text;
begin
  if tg_table_name = 'course_memberships' then
    target_course_id := coalesce(new.course_id, old.course_id);
  elsif tg_table_name = 'course_modules' then
    target_course_id := coalesce(new.course_id, old.course_id);
  elsif tg_table_name = 'module_section_releases' then
    select cm.course_id into target_course_id
      from public.course_modules cm
     where cm.id = coalesce(new.course_module_id, old.course_module_id);
  end if;

  select status into target_status from public.courses where id = target_course_id;
  if target_status <> 'active' then
    raise exception 'course_archived' using errcode = 'object_not_in_prerequisite_state';
  end if;
  if not public.course_metadata_complete(target_course_id) then
    raise exception 'course_metadata_incomplete' using errcode = 'check_violation';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

drop trigger if exists trg_course_memberships_lifecycle_guard on public.course_memberships;
create trigger trg_course_memberships_lifecycle_guard
before insert or update or delete on public.course_memberships
for each row execute function public.guard_course_mutation();

drop trigger if exists trg_course_modules_lifecycle_guard on public.course_modules;
create trigger trg_course_modules_lifecycle_guard
before insert or update or delete on public.course_modules
for each row execute function public.guard_course_mutation();

drop trigger if exists trg_module_section_releases_lifecycle_guard on public.module_section_releases;
create trigger trg_module_section_releases_lifecycle_guard
before insert or update or delete on public.module_section_releases
for each row execute function public.guard_course_mutation();
