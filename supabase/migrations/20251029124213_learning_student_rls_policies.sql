-- Learning RLS: allow students (gustav_limited) to read released course content.

set search_path = public, pg_temp;

create or replace function public.student_is_course_member(
  p_student_sub text,
  p_course_id uuid
)
returns boolean
language sql
security invoker
as $$
  select exists (
    select 1
      from public.course_memberships cm
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
  );
$$;

create or replace function public.student_can_access_unit(
  p_student_sub text,
  p_unit_id uuid
)
returns boolean
language sql
security invoker
as $$
  select exists (
    select 1
      from public.course_modules m
      join public.course_memberships cm on cm.course_id = m.course_id
     where m.unit_id = p_unit_id
       and cm.student_id = p_student_sub
  );
$$;

create or replace function public.student_can_access_course_module(
  p_student_sub text,
  p_course_module_id uuid
)
returns boolean
language sql
security invoker
as $$
  select exists (
    select 1
      from public.course_modules m
      join public.course_memberships cm on cm.course_id = m.course_id
     where m.id = p_course_module_id
       and cm.student_id = p_student_sub
  );
$$;

create or replace function public.student_can_access_section(
  p_student_sub text,
  p_section_id uuid
)
returns boolean
language sql
security invoker
as $$
  select exists (
    select 1
      from public.module_section_releases r
      join public.course_modules m on m.id = r.course_module_id
      join public.course_memberships cm on cm.course_id = m.course_id
     where r.section_id = p_section_id
       and cm.student_id = p_student_sub
       and coalesce(r.visible, false) = true
  );
$$;

drop policy if exists course_modules_select_student on public.course_modules;
create policy course_modules_select_student on public.course_modules
  for select to gustav_limited
  using (
    public.student_is_course_member(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
  );

drop policy if exists units_select_student on public.units;
create policy units_select_student on public.units
  for select to gustav_limited
  using (
    public.student_can_access_unit(
      coalesce(current_setting('app.current_sub', true), ''),
      id
    )
  );

drop policy if exists unit_sections_select_student on public.unit_sections;
create policy unit_sections_select_student on public.unit_sections
  for select to gustav_limited
  using (
    public.student_can_access_section(
      coalesce(current_setting('app.current_sub', true), ''),
      id
    )
  );

drop policy if exists module_section_releases_select_student on public.module_section_releases;
create policy module_section_releases_select_student on public.module_section_releases
  for select to gustav_limited
  using (
    coalesce(visible, false) = true
    and public.student_can_access_course_module(
      coalesce(current_setting('app.current_sub', true), ''),
      course_module_id
    )
  );

drop policy if exists unit_materials_select_student on public.unit_materials;
create policy unit_materials_select_student on public.unit_materials
  for select to gustav_limited
  using (
    public.student_can_access_section(
      coalesce(current_setting('app.current_sub', true), ''),
      section_id
    )
  );

drop policy if exists unit_tasks_select_student on public.unit_tasks;
create policy unit_tasks_select_student on public.unit_tasks
  for select to gustav_limited
  using (
    public.student_can_access_section(
      coalesce(current_setting('app.current_sub', true), ''),
      section_id
    )
  );
