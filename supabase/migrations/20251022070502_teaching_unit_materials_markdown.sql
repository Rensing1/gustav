-- Teaching (Unterrichten) — Markdown materials per unit section
-- Adds unit_materials table with strict RLS, deferrable ordering, and section/unit guard.

create table if not exists public.unit_materials (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.learning_units(id) on delete cascade,
  section_id uuid not null references public.unit_sections(id) on delete cascade,
  title text not null,
  body_md text not null,
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (section_id, position)
);

create index if not exists idx_unit_materials_section on public.unit_materials(section_id);
create index if not exists idx_unit_materials_unit on public.unit_materials(unit_id);

drop trigger if exists trg_unit_materials_updated_at on public.unit_materials;
create trigger trg_unit_materials_updated_at
before update on public.unit_materials
for each row execute function public.set_updated_at();

create or replace function public.unit_materials_section_unit_match()
returns trigger
language plpgsql
as $$
declare
  sec_unit uuid;
begin
  select unit_id into sec_unit from public.unit_sections where id = new.section_id;
  if sec_unit is null then
    raise exception 'section % does not exist', new.section_id using errcode = 'foreign_key_violation';
  end if;
  if sec_unit <> new.unit_id then
    raise exception 'section % belongs to unit %, not %', new.section_id, sec_unit, new.unit_id
      using errcode = 'check_violation';
  end if;
  if tg_op = 'UPDATE' and new.section_id <> old.section_id then
    raise exception 'section_id is immutable' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_unit_materials_section_match on public.unit_materials;
create trigger trg_unit_materials_section_match
before insert or update on public.unit_materials
for each row execute function public.unit_materials_section_unit_match();

-- Ensure deferrable ordering constraint to support transactional reorder operations
alter table public.unit_materials
  drop constraint if exists unit_materials_section_id_position_key;

alter table public.unit_materials
  add constraint unit_materials_section_id_position_key
    unique (section_id, position) deferrable initially immediate;

alter table public.unit_materials enable row level security;

grant select, insert, update, delete on public.unit_materials to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_materials') then
    drop policy if exists unit_materials_select_author on public.unit_materials;
    drop policy if exists unit_materials_insert_author on public.unit_materials;
    drop policy if exists unit_materials_update_author on public.unit_materials;
    drop policy if exists unit_materials_delete_author on public.unit_materials;
  end if;
end $$;

create policy unit_materials_select_author on public.unit_materials
  for select to gustav_limited
  using (
    exists (
      select 1
      from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_materials_insert_author on public.unit_materials
  for insert to gustav_limited
  with check (
    exists (
      select 1
      from public.unit_sections s
      join public.learning_units u on u.id = s.unit_id
      where s.id = section_id
        and u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_materials_update_author on public.unit_materials
  for update to gustav_limited
  using (
    exists (
      select 1
      from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1
      from public.unit_sections s
      join public.learning_units u on u.id = s.unit_id
      where s.id = section_id
        and u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_materials_delete_author on public.unit_materials
  for delete to gustav_limited
  using (
    exists (
      select 1
      from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
