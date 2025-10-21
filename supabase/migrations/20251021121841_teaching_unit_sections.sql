-- Teaching (Unterrichten) — Unit sections within learning units
-- Adds per-unit sections with strict RLS and deferrable unique ordering.

create table if not exists public.unit_sections (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.learning_units(id) on delete cascade,
  title text not null,
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (unit_id, position)
);

create index if not exists idx_unit_sections_unit on public.unit_sections(unit_id);

drop trigger if exists trg_unit_sections_updated_at on public.unit_sections;
create trigger trg_unit_sections_updated_at
before update on public.unit_sections
for each row execute function public.set_updated_at();

alter table public.unit_sections enable row level security;

grant select, insert, update, delete on public.unit_sections to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_sections') then
    drop policy if exists unit_sections_select_author on public.unit_sections;
    drop policy if exists unit_sections_insert_author on public.unit_sections;
    drop policy if exists unit_sections_update_author on public.unit_sections;
    drop policy if exists unit_sections_delete_author on public.unit_sections;
  end if;
end $$;

create policy unit_sections_select_author on public.unit_sections
  for select to gustav_limited
  using (
    exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_sections_insert_author on public.unit_sections
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_sections_update_author on public.unit_sections
  for update to gustav_limited
  using (
    exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_sections_delete_author on public.unit_sections
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

-- Make (unit_id, position) unique constraint deferrable to allow transactional reorders
alter table public.unit_sections
  drop constraint if exists unit_sections_unit_id_position_key;

alter table public.unit_sections
  add constraint unit_sections_unit_id_position_key
    unique (unit_id, position) deferrable initially immediate;
