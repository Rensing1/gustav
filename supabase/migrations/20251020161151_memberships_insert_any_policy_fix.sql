-- Ensure course_memberships insert is allowed for server limited role (gustav_limited)
-- without referencing courses to avoid recursive policy evaluation.

drop policy if exists memberships_insert_owner_only on public.course_memberships;
drop policy if exists memberships_insert_any on public.course_memberships;
create policy memberships_insert_any on public.course_memberships
  for insert to gustav_limited
  with check (true);
