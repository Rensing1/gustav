-- Learning submissions RLS policies enforcing student-only visibility.

set check_function_bodies = off;

do $$
begin
  if exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'learning_submissions'
  ) then
    drop policy if exists learning_submissions_select_self on public.learning_submissions;
    drop policy if exists learning_submissions_insert_guard on public.learning_submissions;
  end if;
end
$$;

create policy learning_submissions_select_self on public.learning_submissions
  for select to gustav_limited
  using (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
  );

create policy learning_submissions_insert_guard on public.learning_submissions
  for insert to gustav_limited
  with check (
    student_sub = coalesce(current_setting('app.current_sub', true), '')
    and public.check_task_visible_to_student(
      coalesce(current_setting('app.current_sub', true), ''),
      course_id,
      task_id
    )
  );

set check_function_bodies = on;
