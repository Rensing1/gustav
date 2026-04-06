-- Align concern box insert policy with the established student membership helper.

drop policy if exists concern_box_entries_insert_member on public.concern_box_entries;
create policy concern_box_entries_insert_member on public.concern_box_entries
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and public.student_is_course_member(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id
    )
  );
