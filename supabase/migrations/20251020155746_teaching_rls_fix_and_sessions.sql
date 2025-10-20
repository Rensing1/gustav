-- Fix RLS recursion and allow app_sessions access for limited role

-- Membership SELECT should not reference courses to avoid recursion with courses policies
drop policy if exists memberships_select_owner_or_self on public.course_memberships;
create policy memberships_select_any on public.course_memberships
  for select to gustav_limited
  using (true);

-- app_sessions policies for limited role (server-side only)
alter table public.app_sessions enable row level security;
grant select, insert, update, delete on public.app_sessions to gustav_limited;
drop policy if exists app_sessions_rw on public.app_sessions;
create policy app_sessions_rw on public.app_sessions
  for all to gustav_limited
  using (true)
  with check (true);
