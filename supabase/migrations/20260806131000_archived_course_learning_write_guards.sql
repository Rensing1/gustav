-- Archived courses remain readable through personal read models but reject new work.

create or replace function public.guard_active_course_learning_write()
returns trigger language plpgsql security definer
set search_path = pg_catalog, public as $$
declare target_course_id uuid;
begin
  -- Already queued analysis may finish after archival under the worker role.
  if current_user = 'gustav_worker' then return new; end if;
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

drop trigger if exists trg_learning_submissions_active_course on public.learning_submissions;
create trigger trg_learning_submissions_active_course
before insert or update on public.learning_submissions
for each row execute function public.guard_active_course_learning_write();

drop trigger if exists trg_dialog_sessions_active_course on public.learning_dialog_sessions;
create trigger trg_dialog_sessions_active_course
before insert on public.learning_dialog_sessions
for each row execute function public.guard_active_course_learning_write();

drop trigger if exists trg_dialog_turns_active_course on public.learning_dialog_turns;
create trigger trg_dialog_turns_active_course
before insert or update on public.learning_dialog_turns
for each row execute function public.guard_active_course_learning_write();

-- Historical evidence must not disappear when an author deletes a task or unit.
alter table public.learning_submissions
  drop constraint if exists learning_submissions_task_id_fkey;
alter table public.learning_submissions
  add constraint learning_submissions_task_id_fkey
  foreign key (task_id) references public.unit_tasks(id) on delete restrict;
