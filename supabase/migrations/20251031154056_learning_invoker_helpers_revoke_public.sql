-- Harden EXECUTE privileges for learning helper functions (SECURITY INVOKER)
-- Context: Earlier migrations granted EXECUTE to gustav_limited but did not
-- explicitly revoke PUBLIC. Make intent explicit and auditable.

set search_path = public, pg_temp;

-- List of helper functions (name and signature) to adjust
-- Note: REVOKE is idempotent; re-grant ensures expected role permissions.

-- next_attempt_nr(uuid, uuid, text)
revoke all on function public.next_attempt_nr(uuid, uuid, text) from public;
grant execute on function public.next_attempt_nr(uuid, uuid, text) to gustav_limited;

-- check_task_visible_to_student(text, uuid, uuid)
revoke all on function public.check_task_visible_to_student(text, uuid, uuid) from public;
grant execute on function public.check_task_visible_to_student(text, uuid, uuid) to gustav_limited;

-- get_released_sections_for_student(text, uuid, integer, integer)
revoke all on function public.get_released_sections_for_student(text, uuid, integer, integer) from public;
grant execute on function public.get_released_sections_for_student(text, uuid, integer, integer) to gustav_limited;

-- get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)
revoke all on function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer) from public;
grant execute on function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer) to gustav_limited;

-- get_released_materials_for_student(text, uuid, uuid)
revoke all on function public.get_released_materials_for_student(text, uuid, uuid) from public;
grant execute on function public.get_released_materials_for_student(text, uuid, uuid) to gustav_limited;

-- get_released_tasks_for_student(text, uuid, uuid)
revoke all on function public.get_released_tasks_for_student(text, uuid, uuid) from public;
grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;

-- get_task_metadata_for_student(text, uuid, uuid)
revoke all on function public.get_task_metadata_for_student(text, uuid, uuid) from public;
grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;

