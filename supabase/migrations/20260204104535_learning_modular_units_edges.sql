-- Modular learning units — edges between modules (graph dependencies).
--
-- Why:
--   Modular units are represented as a graph of modules. The student-facing
--   graph endpoint must be able to return the dependency edges so the UI can
--   render prerequisite arrows and compute k-of-n unlock logic.
--
-- Option B:
--   Modules are identified by `public.unit_modules.id` (module_id), and map
--   1:1 to `public.unit_sections` via `unit_modules.section_id`.
--
-- Security:
--   - Authors can manage edges for their own units only (RLS).
--   - Students can read edges for units they can access (membership via
--     `student_can_access_unit`), but cannot mutate them.
--   - Validation is enforced via a trigger (unit consistency + allowed edge
--     directions).

set check_function_bodies = off;
set search_path = public, pg_temp;

create table if not exists public.unit_module_edges (
  unit_id uuid not null references public.units(id) on delete cascade,
  from_module_id uuid not null references public.unit_modules(id) on delete cascade,
  to_module_id uuid not null references public.unit_modules(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (unit_id, from_module_id, to_module_id),
  constraint unit_module_edges_not_self check (from_module_id <> to_module_id)
);

create index if not exists idx_unit_module_edges_unit_to on public.unit_module_edges(unit_id, to_module_id);
create index if not exists idx_unit_module_edges_unit_from on public.unit_module_edges(unit_id, from_module_id);

drop trigger if exists trg_unit_module_edges_updated_at on public.unit_module_edges;
create trigger trg_unit_module_edges_updated_at
before update on public.unit_module_edges
for each row execute function public.set_updated_at();

create or replace function public.unit_module_edges_validate()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  unit_type text;
  from_phase_id uuid;
  to_phase_id uuid;
  from_pos_in_phase int;
  to_pos_in_phase int;
  from_phase_pos int;
  to_phase_pos int;
begin
  -- Unit must exist and be modular.
  select u.unit_type into unit_type
    from public.units u
   where u.id = new.unit_id;
  if unit_type is null then
    raise exception 'unit % does not exist', new.unit_id using errcode = 'foreign_key_violation';
  end if;
  if unit_type <> 'modular' then
    raise exception 'unit % is not modular', new.unit_id using errcode = 'check_violation';
  end if;

  -- Both module endpoints must belong to the same unit as the edge row.
  select um.phase_id, um.position_in_phase
    into from_phase_id, from_pos_in_phase
    from public.unit_modules um
   where um.id = new.from_module_id
     and um.unit_id = new.unit_id;
  if from_phase_id is null then
    raise exception 'from_module % not in unit %', new.from_module_id, new.unit_id using errcode = 'check_violation';
  end if;

  select um.phase_id, um.position_in_phase
    into to_phase_id, to_pos_in_phase
    from public.unit_modules um
   where um.id = new.to_module_id
     and um.unit_id = new.unit_id;
  if to_phase_id is null then
    raise exception 'to_module % not in unit %', new.to_module_id, new.unit_id using errcode = 'check_violation';
  end if;

  -- Enforce allowed directions: same-phase must go "right", cross-phase only to next phase.
  select p.position into from_phase_pos
    from public.unit_phases p
   where p.id = from_phase_id
     and p.unit_id = new.unit_id;
  select p.position into to_phase_pos
    from public.unit_phases p
   where p.id = to_phase_id
     and p.unit_id = new.unit_id;
  if from_phase_pos is null or to_phase_pos is null then
    raise exception 'phase mismatch for unit %', new.unit_id using errcode = 'check_violation';
  end if;

  if from_phase_id = to_phase_id then
    if not (from_pos_in_phase < to_pos_in_phase) then
      raise exception 'same-phase edge must go right (% -> %)', new.from_module_id, new.to_module_id using errcode = 'check_violation';
    end if;
  else
    if not (to_phase_pos = from_phase_pos + 1) then
      raise exception 'cross-phase edge must target next phase (% -> %)', new.from_module_id, new.to_module_id using errcode = 'check_violation';
    end if;
  end if;

  -- Edges are immutable; updates should be delete+insert.
  if tg_op = 'UPDATE' then
    if new.unit_id <> old.unit_id
      or new.from_module_id <> old.from_module_id
      or new.to_module_id <> old.to_module_id then
      raise exception 'edge identifiers are immutable' using errcode = 'check_violation';
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_unit_module_edges_validate on public.unit_module_edges;
create trigger trg_unit_module_edges_validate
before insert or update on public.unit_module_edges
for each row execute function public.unit_module_edges_validate();

alter table public.unit_module_edges enable row level security;
grant select, insert, update, delete on public.unit_module_edges to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_module_edges') then
    drop policy if exists unit_module_edges_select_author on public.unit_module_edges;
    drop policy if exists unit_module_edges_insert_author on public.unit_module_edges;
    drop policy if exists unit_module_edges_update_author on public.unit_module_edges;
    drop policy if exists unit_module_edges_delete_author on public.unit_module_edges;
    drop policy if exists unit_module_edges_select_student on public.unit_module_edges;
  end if;
end $$;

create policy unit_module_edges_select_author on public.unit_module_edges
  for select to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_module_edges_insert_author on public.unit_module_edges
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
        and u.unit_type = 'modular'
    )
  );

create policy unit_module_edges_update_author on public.unit_module_edges
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

create policy unit_module_edges_delete_author on public.unit_module_edges
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_module_edges_select_student on public.unit_module_edges
  for select to gustav_limited
  using (
    public.student_can_access_unit(
      coalesce(current_setting('app.current_sub', true), ''),
      unit_id
    )
  );

set check_function_bodies = on;
