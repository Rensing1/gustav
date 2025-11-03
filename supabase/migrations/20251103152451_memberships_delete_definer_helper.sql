
create or replace function public.remove_course_membership(
  p_owner   text,
  p_course  uuid,
  p_student text
)
returns void
language sql
security definer
set search_path = public
as $$
  -- SECURITY NOTE:
  -- Bind authorization to the session: require that the provided `p_owner`
  -- matches the current session subject, and that this subject owns the
  -- course. This prevents spoofing by passing an arbitrary `p_owner`.
  delete from public.course_memberships m
  where m.course_id = p_course
    and m.student_id = p_student
    and p_owner = coalesce(current_setting('app.current_sub', true), '')
    and exists (
      select 1 from public.courses c
      where c.id = p_course
        and c.teacher_id = p_owner
    );
$$;

grant execute on function public.remove_course_membership(text, uuid, text) to gustav_limited;
