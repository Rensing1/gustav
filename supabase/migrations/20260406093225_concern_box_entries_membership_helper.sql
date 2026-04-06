-- Use a dedicated helper so concern box insert checks do not depend on caller-side RLS visibility.

set search_path = public, pg_temp;

create or replace function public.concern_box_student_is_course_member(
  p_student_sub text,
  p_course_id uuid
)
returns boolean
language sql
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
      from public.course_memberships cm
     where cm.course_id = p_course_id
       and cm.student_id = p_student_sub
  );
$$;

revoke all on function public.concern_box_student_is_course_member(text, uuid) from public;
grant execute on function public.concern_box_student_is_course_member(text, uuid) to gustav_limited;

drop policy if exists concern_box_entries_insert_member on public.concern_box_entries;
create policy concern_box_entries_insert_member on public.concern_box_entries
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and public.concern_box_student_is_course_member(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
  );
