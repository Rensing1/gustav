-- Enforce RLS for course_memberships delete and refresh policies for owner-only access

alter table if exists public.course_memberships force row level security;

-- Ensure SELECT exposes rows to owners or the student so DELETE can operate without
-- leaking other memberships.
drop policy if exists memberships_select_self_only on public.course_memberships;
create policy memberships_select_owner_or_self on public.course_memberships
  for select to gustav_limited
  using (
    course_memberships.student_id = coalesce(current_setting('app.current_sub', true), '')
    or public.course_exists_for_owner(
      coalesce(current_setting('app.current_sub', true), ''),
      course_memberships.course_id
    )
  );

-- Recreate delete policy to ensure only the owner can delete memberships.
-- Note: Some Postgres variants do not support AS RESTRICTIVE; we keep a single
-- delete policy to avoid permissive combinations.
drop policy if exists memberships_delete_owner_only on public.course_memberships;
create policy memberships_delete_owner_only on public.course_memberships
  for delete to gustav_limited
  using (
    exists (
      select 1 from public.courses c
      where c.id = course_id
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    )
  );
