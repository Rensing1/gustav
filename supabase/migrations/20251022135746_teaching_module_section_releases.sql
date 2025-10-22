-- Teaching (Unterrichten) — Section release toggles per course module
-- Adds persistent visibility state with strict RLS guarding course ownership.

create table if not exists public.module_section_releases (
  course_module_id uuid not null references public.course_modules(id) on delete cascade,
  section_id uuid not null references public.unit_sections(id) on delete cascade,
  visible boolean not null,
  released_at timestamptz null,
  released_by text null,
  constraint module_section_releases_pkey primary key (course_module_id, section_id)
);

create index if not exists idx_module_section_releases_module on public.module_section_releases(course_module_id);
create index if not exists idx_module_section_releases_section on public.module_section_releases(section_id);

alter table public.module_section_releases enable row level security;

grant select, insert, update, delete on public.module_section_releases to gustav_limited;

do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'module_section_releases'
  ) then
    drop policy if exists module_section_releases_select_owner on public.module_section_releases;
    drop policy if exists module_section_releases_insert_owner on public.module_section_releases;
    drop policy if exists module_section_releases_update_owner on public.module_section_releases;
    drop policy if exists module_section_releases_delete_owner on public.module_section_releases;
  end if;
end
$$;

create policy module_section_releases_select_owner on public.module_section_releases
  for select to gustav_limited
  using (
    exists (
      select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      where m.id = course_module_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy module_section_releases_insert_owner on public.module_section_releases
  for insert to gustav_limited
  with check (
    exists (
      select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      join public.unit_sections s on s.id = section_id
      where m.id = course_module_id
        and s.unit_id = m.unit_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
    and released_by = coalesce(current_setting('app.current_sub', true), '')
  );

create policy module_section_releases_update_owner on public.module_section_releases
  for update to gustav_limited
  using (
    exists (
      select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      where m.id = course_module_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      join public.unit_sections s on s.id = section_id
      where m.id = course_module_id
        and s.unit_id = m.unit_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
    and released_by = coalesce(current_setting('app.current_sub', true), '')
  );

create policy module_section_releases_delete_owner on public.module_section_releases
  for delete to gustav_limited
  using (
    exists (
      select 1
      from public.course_modules m
      join public.courses c on c.id = m.course_id
      where m.id = course_module_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
