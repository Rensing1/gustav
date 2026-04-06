-- Insert concern box entries through a dedicated function to keep membership checks explicit.

set search_path = public, pg_temp;

create or replace function public.create_concern_box_entry(
  p_student_sub text,
  p_course_id uuid,
  p_message_text text,
  p_anonymous boolean
)
returns table(id uuid, created_at timestamptz)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if p_student_sub is null or btrim(p_student_sub) = '' then
    return;
  end if;

  if p_message_text is null or btrim(p_message_text) = '' then
    return;
  end if;

  if not public.concern_box_student_is_course_member(p_student_sub, p_course_id) then
    return;
  end if;

  return query
  insert into public.concern_box_entries(course_id, student_sub, message_text, anonymous)
  values (p_course_id, p_student_sub, btrim(p_message_text), coalesce(p_anonymous, true))
  returning concern_box_entries.id, concern_box_entries.created_at;
end;
$$;

revoke all on function public.create_concern_box_entry(text, uuid, text, boolean) from public;
grant execute on function public.create_concern_box_entry(text, uuid, text, boolean) to gustav_limited;
