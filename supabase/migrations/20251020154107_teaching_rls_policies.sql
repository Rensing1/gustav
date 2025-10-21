-- Teaching RLS policies and limited role for server-side access

-- Create limited app role if not exists
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'gustav_limited') then
    create role gustav_limited login password 'gustav-limited';
  end if;
end $$;

grant usage on schema public to gustav_limited;
grant select, insert, update, delete on public.courses to gustav_limited;
grant select, insert, update, delete on public.course_memberships to gustav_limited;

-- Helper: ensure RLS enabled (idempotent)
alter table public.courses enable row level security;
alter table public.course_memberships enable row level security;

-- Clean existing policies to allow re-run (safe in dev)
do $$ begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='courses') then
    drop policy if exists courses_select_owner on public.courses;
    drop policy if exists courses_select_member on public.courses;
    drop policy if exists courses_insert_owner on public.courses;
    drop policy if exists courses_update_owner on public.courses;
    drop policy if exists courses_delete_owner on public.courses;
  end if;
  if exists (select 1 from pg_policies where schemaname='public' and tablename='course_memberships') then
    drop policy if exists memberships_select_owner_or_self on public.course_memberships;
    drop policy if exists memberships_insert_owner_only on public.course_memberships;
    drop policy if exists memberships_delete_owner_only on public.course_memberships;
  end if;
end $$;

-- Policies for courses
create policy courses_select_owner on public.courses
  for select to gustav_limited
  using (teacher_id = coalesce(current_setting('app.current_sub', true), ''));

create policy courses_select_member on public.courses
  for select to gustav_limited
  using (exists (
    select 1 from public.course_memberships m
    where m.course_id = id and m.student_id = coalesce(current_setting('app.current_sub', true), '')
  ));

create policy courses_insert_owner on public.courses
  for insert to gustav_limited
  with check (teacher_id = coalesce(current_setting('app.current_sub', true), ''));

create policy courses_update_owner on public.courses
  for update to gustav_limited
  using (teacher_id = coalesce(current_setting('app.current_sub', true), ''))
  with check (teacher_id = coalesce(current_setting('app.current_sub', true), ''));

create policy courses_delete_owner on public.courses
  for delete to gustav_limited
  using (teacher_id = coalesce(current_setting('app.current_sub', true), ''));

-- Policies for memberships
create policy memberships_select_owner_or_self on public.course_memberships
  for select to gustav_limited
  using (
    exists (select 1 from public.courses c where c.id = course_id and c.teacher_id = coalesce(current_setting('app.current_sub', true), ''))
    or student_id = coalesce(current_setting('app.current_sub', true), '')
  );

create policy memberships_insert_owner_only on public.course_memberships
  for insert to gustav_limited
  with check (
    exists (select 1 from public.courses c where c.id = course_id and c.teacher_id = coalesce(current_setting('app.current_sub', true), ''))
  );

create policy memberships_delete_owner_only on public.course_memberships
  for delete to gustav_limited
  using (
    exists (select 1 from public.courses c where c.id = course_id and c.teacher_id = coalesce(current_setting('app.current_sub', true), ''))
  );
