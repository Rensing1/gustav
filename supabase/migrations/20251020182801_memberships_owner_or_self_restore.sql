-- Restore secure SELECT policy for course_memberships and helper for owner roster

-- Remove insecure variants introduced by previous hotfix
drop policy if exists memberships_select_any on public.course_memberships;
drop policy if exists memberships_select_self_only on public.course_memberships;
drop policy if exists memberships_select_owner_or_self on public.course_memberships;

-- Reinstate self-only visibility to prevent recursive policies.
create policy memberships_select_self_only on public.course_memberships
  for select to gustav_limited
  using (student_id = coalesce(current_setting('app.current_sub', true), ''));

-- SECURITY DEFINER helper: allows owners to list their members without RLS recursion
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
  limit least(greatest(coalesce(p_limit, 20), 1), 50)
  offset greatest(coalesce(p_offset, 0), 0)
$$;

grant execute on function public.get_course_members(text, uuid, integer, integer) to gustav_limited;
-- Helper clamp tightened: ensure limit within 1..50, default 20.
