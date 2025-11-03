
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
  -- Authorize strictly via the session subject (app.current_sub). The `p_owner`
  -- parameter is kept for compatibility but ignored for authorization, so callers
  -- cannot escalate by spoofing a different owner identity.
  delete from public.course_memberships m
  where m.course_id = p_course
    and m.student_id = p_student
    and exists (
      select 1 from public.courses c
      where c.id = p_course
        and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
    );
$$;

grant execute on function public.remove_course_membership(text, uuid, text) to gustav_limited;
