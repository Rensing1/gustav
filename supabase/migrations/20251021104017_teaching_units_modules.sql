-- Teaching (Unterrichten) — Learning units & course modules
-- Adds reusable content units and per-course module ordering with strict RLS.

create table if not exists public.learning_units (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  summary text null,
  author_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_learning_units_author on public.learning_units(author_id);

drop trigger if exists trg_learning_units_updated_at on public.learning_units;
create trigger trg_learning_units_updated_at
before update on public.learning_units
for each row execute function public.set_updated_at();

create table if not exists public.course_modules (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  unit_id uuid not null references public.learning_units(id) on delete cascade,
  position integer not null check (position > 0),
  context_notes text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (course_id, position),
  unique (course_id, unit_id)
);

create index if not exists idx_course_modules_course on public.course_modules(course_id);
create index if not exists idx_course_modules_unit on public.course_modules(unit_id);

drop trigger if exists trg_course_modules_updated_at on public.course_modules;
create trigger trg_course_modules_updated_at
before update on public.course_modules
for each row execute function public.set_updated_at();

alter table public.learning_units enable row level security;
alter table public.course_modules enable row level security;

grant select, insert, update, delete on public.learning_units to gustav_limited;
grant select, insert, update, delete on public.course_modules to gustav_limited;

do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='learning_units') then
    drop policy if exists learning_units_select_author on public.learning_units;
    drop policy if exists learning_units_insert_author on public.learning_units;
    drop policy if exists learning_units_update_author on public.learning_units;
    drop policy if exists learning_units_delete_author on public.learning_units;
  end if;
  if exists (select 1 from pg_policies where schemaname='public' and tablename='course_modules') then
    drop policy if exists course_modules_select_owner on public.course_modules;
    drop policy if exists course_modules_insert_owner on public.course_modules;
    drop policy if exists course_modules_update_owner on public.course_modules;
    drop policy if exists course_modules_delete_owner on public.course_modules;
  end if;
end $$;

create policy learning_units_select_author on public.learning_units
  for select to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy learning_units_insert_author on public.learning_units
  for insert to gustav_limited
  with check (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy learning_units_update_author on public.learning_units
  for update to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''))
  with check (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy learning_units_delete_author on public.learning_units
  for delete to gustav_limited
  using (author_id = coalesce(current_setting('app.current_sub', true), ''));

create policy course_modules_select_owner on public.course_modules
  for select to gustav_limited
  using (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy course_modules_insert_owner on public.course_modules
  for insert to gustav_limited
  with check (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
    and exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy course_modules_update_owner on public.course_modules
  for update to gustav_limited
  using (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  )
  with check (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
    and exists (
      select 1 from public.learning_units u
      where u.id = unit_id
        and u.author_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create policy course_modules_delete_owner on public.course_modules
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );

create or replace function public.unit_exists_for_author(
  p_author text,
  p_unit uuid
)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.learning_units
    where id = p_unit
      and author_id = p_author
  );
$$;

create or replace function public.unit_exists(p_unit uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.learning_units
    where id = p_unit
  );
$$;

grant execute on function public.unit_exists_for_author(text, uuid) to gustav_limited;
grant execute on function public.unit_exists(uuid) to gustav_limited;
