-- Teaching helpers for existence and ownership checks (SECURITY DEFINER)

create or replace function public.course_exists_for_owner(
  p_owner text,
  p_course uuid
)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.courses c where c.id = p_course and c.teacher_id = p_owner
  );
$$;

grant execute on function public.course_exists_for_owner(text, uuid) to gustav_limited;


create or replace function public.course_exists(
  p_course uuid
)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.courses where id = p_course
  );
$$;

grant execute on function public.course_exists(uuid) to gustav_limited;
