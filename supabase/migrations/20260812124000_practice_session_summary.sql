-- Learning: add durable practice-session completion reasons and module labels.

set check_function_bodies = off;
set search_path = public, pg_temp;

alter table public.learning_practice_session_items
  add column module_title text;

update public.learning_practice_session_items item
   set module_title = section.title
  from public.unit_modules module
  join public.unit_sections section on section.id = module.section_id
 where module.id = item.practice_module_id;

update public.learning_practice_session_items
   set module_title = 'Übung'
 where module_title is null or btrim(module_title) = '';

alter table public.learning_practice_session_items
  alter column module_title set not null;

alter table public.learning_practice_sessions
  add column end_reason text;

update public.learning_practice_sessions session
   set end_reason = case
     when not exists (
       select 1
         from public.learning_practice_session_items item
        where item.session_id = session.id
     ) then 'empty'
     else 'completed'
   end
 where session.status = 'ended';

alter table public.learning_practice_sessions
  add constraint learning_practice_sessions_end_reason_check
  check (
    (status = 'active' and end_reason is null)
    or
    (status = 'ended' and end_reason in ('completed', 'stopped', 'empty'))
  ) not valid;

alter table public.learning_practice_sessions
  validate constraint learning_practice_sessions_end_reason_check;

set check_function_bodies = on;
