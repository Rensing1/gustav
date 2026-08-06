-- Archive a teacher-selected batch as one all-or-nothing transaction.

create or replace function public.archive_courses_owned(p_course_ids uuid[], p_owner_sub text)
returns setof public.courses language plpgsql security definer
set search_path = pg_catalog, public as $$
declare course_id uuid; archived public.courses;
begin
  if coalesce(array_length(p_course_ids, 1), 0) < 1 or array_length(p_course_ids, 1) > 100 then
    raise exception 'invalid_course_batch' using errcode = 'check_violation';
  end if;
  foreach course_id in array p_course_ids loop
    archived := public.archive_course_owned(course_id, p_owner_sub);
    return next archived;
  end loop;
end;
$$;

revoke all on function public.archive_courses_owned(uuid[], text) from public;
grant execute on function public.archive_courses_owned(uuid[], text) to gustav_limited;
