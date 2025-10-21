-- Restore owner-only insert control for course_memberships.
-- Ensures gustav_limited clients can only insert when they own the course.

drop policy if exists memberships_insert_any on public.course_memberships;
drop policy if exists memberships_insert_owner_only on public.course_memberships;

create policy memberships_insert_owner_only on public.course_memberships
  for insert to gustav_limited
  with check (
    exists (
      select 1
      from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
