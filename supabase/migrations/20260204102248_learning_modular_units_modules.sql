-- Modular learning units — phases + modules metadata and safe per-section counts.
--
-- Why:
--   We introduce modular learning units where students navigate a graph of
--   "modules". A module is a graph node with its own UUID (module_id) but
--   its *content* (tasks/materials) lives in an existing unit section.
--
-- Option B (decision):
--   `public.unit_modules.id` is the module_id used by the Learning API and
--   maps 1:1 to `public.unit_sections.id` via `unit_modules.section_id`.
--
-- Security:
--   - Keep content (unit_tasks/unit_materials) fail-closed for students unless
--     the Learning backend sets `app.current_course_id` and the unit is modular.
--   - Module/phase metadata is safe to expose to enrolled students.

set check_function_bodies = off;

-- ---------------------------------------------------------------------------
-- 1) Safe counts on unit_sections (avoid content leak in graphs)
-- ---------------------------------------------------------------------------

alter table public.unit_sections
  add column if not exists tasks_total integer not null default 0 check (tasks_total >= 0);

alter table public.unit_sections
  add column if not exists materials_count integer not null default 0 check (materials_count >= 0);

-- Backfill existing rows (one-time).
update public.unit_sections s
set tasks_total = (
      select count(*)::int
      from public.unit_tasks t
      where t.section_id = s.id
    ),
    materials_count = (
      select count(*)::int
      from public.unit_materials m
      where m.section_id = s.id
    );

create or replace function public.refresh_unit_section_tasks_total(p_section_id uuid)
returns void
language sql
security invoker
set search_path = public, pg_temp
as $$
  update public.unit_sections s
     set tasks_total = (
           select count(*)::int
           from public.unit_tasks t
           where t.section_id = p_section_id
         )
   where s.id = p_section_id;
$$;

create or replace function public.refresh_unit_section_materials_count(p_section_id uuid)
returns void
language sql
security invoker
set search_path = public, pg_temp
as $$
  update public.unit_sections s
     set materials_count = (
           select count(*)::int
           from public.unit_materials m
           where m.section_id = p_section_id
         )
   where s.id = p_section_id;
$$;

create or replace function public.trg_unit_tasks_refresh_section_tasks_total()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  sid uuid;
begin
  sid := coalesce(new.section_id, old.section_id);
  perform public.refresh_unit_section_tasks_total(sid);
  return null;
end;
$$;

drop trigger if exists trg_unit_tasks_refresh_section_tasks_total on public.unit_tasks;
create trigger trg_unit_tasks_refresh_section_tasks_total
after insert or delete on public.unit_tasks
for each row execute function public.trg_unit_tasks_refresh_section_tasks_total();

create or replace function public.trg_unit_materials_refresh_section_materials_count()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  sid uuid;
begin
  sid := coalesce(new.section_id, old.section_id);
  perform public.refresh_unit_section_materials_count(sid);
  return null;
end;
$$;

drop trigger if exists trg_unit_materials_refresh_section_materials_count on public.unit_materials;
create trigger trg_unit_materials_refresh_section_materials_count
after insert or delete on public.unit_materials
for each row execute function public.trg_unit_materials_refresh_section_materials_count();

-- ---------------------------------------------------------------------------
-- 2) Modular phases
-- ---------------------------------------------------------------------------

create table if not exists public.unit_phases (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.units(id) on delete cascade,
  title text not null,
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (unit_id, position)
);

create index if not exists idx_unit_phases_unit on public.unit_phases(unit_id);

drop trigger if exists trg_unit_phases_updated_at on public.unit_phases;
create trigger trg_unit_phases_updated_at
before update on public.unit_phases
for each row execute function public.set_updated_at();

alter table public.unit_phases enable row level security;
grant select, insert, update, delete on public.unit_phases to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_phases') then
    drop policy if exists unit_phases_select_author on public.unit_phases;
    drop policy if exists unit_phases_insert_author on public.unit_phases;
    drop policy if exists unit_phases_update_author on public.unit_phases;
    drop policy if exists unit_phases_delete_author on public.unit_phases;
    drop policy if exists unit_phases_select_student on public.unit_phases;
  end if;
end $$;

create policy unit_phases_select_author on public.unit_phases
  for select to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_phases_insert_author on public.unit_phases
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
        and u.unit_type = 'modular'
    )
  );

create policy unit_phases_update_author on public.unit_phases
  for update to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
        and u.unit_type = 'modular'
    )
  );

create policy unit_phases_delete_author on public.unit_phases
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_phases_select_student on public.unit_phases
  for select to gustav_limited
  using (
    public.student_can_access_unit(
      coalesce(current_setting('app.current_sub', true), ''),
      unit_id
    )
  );

-- Make (unit_id, position) deferrable to allow transactional reorders.
alter table public.unit_phases
  drop constraint if exists unit_phases_unit_id_position_key;

alter table public.unit_phases
  add constraint unit_phases_unit_id_position_key
    unique (unit_id, position) deferrable initially immediate;

-- ---------------------------------------------------------------------------
-- 3) Modular modules (graph nodes) mapping 1:1 to unit_sections
-- ---------------------------------------------------------------------------

create table if not exists public.unit_modules (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.units(id) on delete cascade,
  section_id uuid not null references public.unit_sections(id) on delete cascade,
  phase_id uuid not null references public.unit_phases(id) on delete cascade,
  position_in_phase integer not null check (position_in_phase > 0),
  required_prereq_count integer not null default 0 check (required_prereq_count >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (section_id),
  unique (phase_id, position_in_phase)
);

create index if not exists idx_unit_modules_unit on public.unit_modules(unit_id);
create index if not exists idx_unit_modules_phase on public.unit_modules(phase_id);

drop trigger if exists trg_unit_modules_updated_at on public.unit_modules;
create trigger trg_unit_modules_updated_at
before update on public.unit_modules
for each row execute function public.set_updated_at();

alter table public.unit_modules enable row level security;
grant select, insert, update, delete on public.unit_modules to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_modules') then
    drop policy if exists unit_modules_select_author on public.unit_modules;
    drop policy if exists unit_modules_insert_author on public.unit_modules;
    drop policy if exists unit_modules_update_author on public.unit_modules;
    drop policy if exists unit_modules_delete_author on public.unit_modules;
    drop policy if exists unit_modules_select_student on public.unit_modules;
  end if;
end $$;

create policy unit_modules_select_author on public.unit_modules
  for select to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_modules_insert_author on public.unit_modules
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
        and u.unit_type = 'modular'
    )
    and exists (
      select 1 from public.unit_sections s
      where s.id = section_id
        and s.unit_id = unit_id
    )
    and exists (
      select 1 from public.unit_phases p
      where p.id = phase_id
        and p.unit_id = unit_id
    )
  );

create policy unit_modules_update_author on public.unit_modules
  for update to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
        and u.unit_type = 'modular'
    )
    and exists (
      select 1 from public.unit_sections s
      where s.id = section_id
        and s.unit_id = unit_id
    )
    and exists (
      select 1 from public.unit_phases p
      where p.id = phase_id
        and p.unit_id = unit_id
    )
  );

create policy unit_modules_delete_author on public.unit_modules
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_modules_select_student on public.unit_modules
  for select to gustav_limited
  using (
    public.student_can_access_unit(
      coalesce(current_setting('app.current_sub', true), ''),
      unit_id
    )
  );

alter table public.unit_modules
  drop constraint if exists unit_modules_phase_id_position_in_phase_key;

alter table public.unit_modules
  add constraint unit_modules_phase_id_position_in_phase_key
    unique (phase_id, position_in_phase) deferrable initially immediate;

-- ---------------------------------------------------------------------------
-- 4) Extend student_can_access_section to support modular units (course-scoped)
-- ---------------------------------------------------------------------------

create or replace function public.student_can_access_section(
  p_student_sub text,
  p_section_id uuid
)
returns boolean
language sql
security invoker
set search_path = public, pg_temp
as $$
  with ctx as (
    select case
      when coalesce(current_setting('app.current_course_id', true), '') ~* '^[0-9a-f-]{36}$'
        then current_setting('app.current_course_id', true)::uuid
      else null
    end as course_id
  )
  select
    -- Linear: released section in the course.
    exists (
      select 1
        from public.module_section_releases r
        join public.course_modules m on m.id = r.course_module_id
        join public.course_memberships cm on cm.course_id = m.course_id
       where r.section_id = p_section_id
         and cm.student_id = p_student_sub
         and coalesce(r.visible, false) = true
    )
    or
    -- Modular: section belongs to a modular unit attached to the *current* course
    -- and is mapped as a module (Option B).
    exists (
      select 1
        from public.unit_sections s
        join public.units u on u.id = s.unit_id
        join public.unit_modules um on um.section_id = s.id
        join public.course_modules m on m.unit_id = s.unit_id
        join public.course_memberships cm on cm.course_id = m.course_id
        join ctx on true
       where s.id = p_section_id
         and u.unit_type = 'modular'
         and cm.student_id = p_student_sub
         and m.course_id = ctx.course_id
    );
$$;

-- SECURITY: lock down helper functions.
revoke all on function public.refresh_unit_section_tasks_total(uuid) from public;
revoke all on function public.refresh_unit_section_materials_count(uuid) from public;
grant execute on function public.refresh_unit_section_tasks_total(uuid) to gustav_limited;
grant execute on function public.refresh_unit_section_materials_count(uuid) to gustav_limited;

set check_function_bodies = on;
