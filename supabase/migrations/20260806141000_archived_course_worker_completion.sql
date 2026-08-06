-- Let already queued analysis jobs finish after their course is archived.
--
-- Worker update functions are SECURITY DEFINER. Inside their triggers,
-- current_user is therefore the function owner, while session_user still
-- identifies the dedicated worker login.

create or replace function public.guard_active_course_learning_write()
returns trigger language plpgsql security definer
set search_path = pg_catalog, public as $$
declare target_course_id uuid;
begin
  if session_user = 'gustav_worker' then return new; end if;
  if tg_table_name = 'learning_dialog_turns' then
    select s.course_id into target_course_id from public.learning_dialog_sessions s
     where s.id = new.session_id and s.status = 'active';
  else
    target_course_id := new.course_id;
  end if;
  if target_course_id is null or not exists (
    select 1 from public.courses c where c.id = target_course_id and c.status = 'active'
  ) then
    raise exception 'course_archived' using errcode = 'object_not_in_prerequisite_state';
  end if;
  return new;
end;
$$;
