-- Teaching (Unterrichten) — Tasks per unit section (Markdown MVP)
-- Introduces unit_tasks table with RLS enforcing author ownership and
-- deferrable ordering for atomic reorder operations.

create table if not exists public.unit_tasks (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.units(id) on delete cascade,
  section_id uuid not null references public.unit_sections(id) on delete cascade,
  instruction_md text not null,
  criteria text[] not null default '{}',
  hints_md text null,
  due_at timestamptz null,
  max_attempts integer null check (max_attempts > 0),
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (section_id, position)
);

alter table public.unit_tasks
  add constraint unit_tasks_instruction_not_blank
    check (length(btrim(instruction_md)) > 0);

alter table public.unit_tasks
  add constraint unit_tasks_criteria_length
    check (array_length(criteria, 1) <= 10);

alter table public.unit_tasks
  add constraint unit_tasks_criteria_entries_not_blank
    check (array_position(criteria, '') is null);

create index if not exists idx_unit_tasks_section on public.unit_tasks(section_id);
create index if not exists idx_unit_tasks_unit on public.unit_tasks(unit_id);

drop trigger if exists trg_unit_tasks_updated_at on public.unit_tasks;
create trigger trg_unit_tasks_updated_at
before update on public.unit_tasks
for each row execute function public.set_updated_at();

create or replace function public.unit_tasks_section_unit_match()
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

drop trigger if exists trg_unit_tasks_section_match on public.unit_tasks;
create trigger trg_unit_tasks_section_match
before insert or update on public.unit_tasks
for each row execute function public.unit_tasks_section_unit_match();

alter table public.unit_tasks
  drop constraint if exists unit_tasks_section_id_position_key;

alter table public.unit_tasks
  add constraint unit_tasks_section_id_position_key
    unique (section_id, position) deferrable initially immediate;

alter table public.unit_tasks enable row level security;

grant select, insert, update, delete on public.unit_tasks to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='unit_tasks') then
    drop policy if exists unit_tasks_select_author on public.unit_tasks;
    drop policy if exists unit_tasks_insert_author on public.unit_tasks;
    drop policy if exists unit_tasks_update_author on public.unit_tasks;
    drop policy if exists unit_tasks_delete_author on public.unit_tasks;
  end if;
end $$;

create policy unit_tasks_select_author on public.unit_tasks
  for select to gustav_limited
  using (
    exists (
      select 1
      from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_tasks_insert_author on public.unit_tasks
  for insert to gustav_limited
  with check (
    exists (
      select 1
      from public.unit_sections s
      join public.units u on u.id = s.unit_id
      where s.id = section_id
        and u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_tasks_update_author on public.unit_tasks
  for update to gustav_limited
  using (
    exists (
      select 1
      from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1
      from public.unit_sections s
      join public.units u on u.id = s.unit_id
      where s.id = section_id
        and u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy unit_tasks_delete_author on public.unit_tasks
  for delete to gustav_limited
  using (
    exists (
      select 1
      from public.units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
