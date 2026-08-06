-- Active rosters exclude former members; archived rosters preserve them.

create or replace function public.get_course_members(
  p_owner text, p_course uuid, p_limit integer, p_offset integer
)
returns table(student_id text, created_at timestamptz)
language sql security definer set search_path = pg_catalog, public as $$
  select m.student_id, m.created_at
    from public.course_memberships m
    join public.courses c on c.id = m.course_id
   where m.course_id = p_course and c.teacher_id = p_owner
     and (c.status = 'archived' or m.ended_at is null)
   order by m.created_at asc, m.student_id
   limit least(greatest(coalesce(p_limit, 20), 1), 50)
  offset greatest(coalesce(p_offset, 0), 0);
$$;

revoke all on function public.get_course_members(text, uuid, integer, integer) from public;
grant execute on function public.get_course_members(text, uuid, integer, integer) to gustav_limited;
