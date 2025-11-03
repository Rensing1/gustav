-- SECURITY DEFINER helper to remove a course membership as the owner

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
  delete from public.course_memberships m
  where m.course_id = p_course
    and m.student_id = p_student
    and exists (
      select 1 from public.courses c
      where c.id = p_course and c.teacher_id = p_owner
    );
$$;

grant execute on function public.remove_course_membership(text, uuid, text) to gustav_limited;

