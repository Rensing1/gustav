-- Ensure owner can read course memberships while avoiding recursive RLS

drop policy if exists memberships_select_self_only on public.course_memberships;
drop policy if exists memberships_select_any on public.course_memberships;
drop policy if exists memberships_select_owner_or_self on public.course_memberships;

create policy memberships_select_any on public.course_memberships
  for select to gustav_limited
  using (true);
