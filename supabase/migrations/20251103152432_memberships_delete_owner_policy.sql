-- Restore/ensure delete policy for course_memberships so owners can unenroll students under RLS

-- Idempotent safety: enable RLS and refresh the delete policy
alter table if exists public.course_memberships enable row level security;

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

-- Optional: keep privileges consistent (grants may already exist from earlier migrations)
grant delete on public.course_memberships to gustav_limited;

