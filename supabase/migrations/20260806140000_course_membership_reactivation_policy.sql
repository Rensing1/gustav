-- Owners may reactivate a former membership through the guarded upsert path.

drop policy if exists memberships_update_owner_only on public.course_memberships;
create policy memberships_update_owner_only on public.course_memberships
  for update to gustav_limited
  using (
    public.course_exists_for_owner(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
  )
  with check (
    public.course_exists_for_owner(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
  );
