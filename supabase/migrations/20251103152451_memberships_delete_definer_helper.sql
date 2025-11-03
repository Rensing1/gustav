
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
  -- We intentionally ignore the p_owner argument for authorization and instead
  -- bind ownership to the current session via app.current_sub. This prevents
  -- callers from spoofing the owner by passing an arbitrary p_owner value.
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
