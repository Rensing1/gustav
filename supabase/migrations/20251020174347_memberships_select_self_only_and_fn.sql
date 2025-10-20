-- Restrict course_memberships SELECT to self-only and provide
-- a SECURITY DEFINER helper for owner member listing without RLS recursion.

-- Replace permissive SELECT policy with self-only
drop policy if exists memberships_select_any on public.course_memberships;
drop policy if exists memberships_select_owner_or_self on public.course_memberships;
create policy memberships_select_self_only on public.course_memberships
  for select to gustav_limited
  using (student_id = coalesce(current_setting('app.current_sub', true), ''));

-- SECURITY DEFINER helper to list members as the course owner.
-- Runs with definer privileges (created by migration user, typically table owner),
-- so it is not constrained by RLS on course_memberships. Ownership is verified inside.
create or replace function public.get_course_members(
  p_owner text,
  p_course uuid,
  p_limit integer,
  p_offset integer
)
returns table(student_id text, created_at timestamptz)
language sql
security definer
set search_path = public
as $$
  select m.student_id, m.created_at
  from public.course_memberships m
  where m.course_id = p_course
    and exists (
      select 1 from public.courses c
      where c.id = p_course and c.teacher_id = p_owner
    )
  order by m.created_at asc, m.student_id
  limit least(coalesce(p_limit, 50), 50)
  offset greatest(coalesce(p_offset, 0), 0)
$$;

grant execute on function public.get_course_members(text, uuid, integer, integer) to gustav_limited;
