-- Ensure course_memberships INSERT remains allowed for the limited app role
-- to avoid RLS recursion with courses policies. App enforces owner checks.

drop policy if exists memberships_insert_owner_only on public.course_memberships;
drop policy if exists memberships_insert_any on public.course_memberships;
create policy memberships_insert_any on public.course_memberships
  for insert to gustav_limited
  with check (true);
