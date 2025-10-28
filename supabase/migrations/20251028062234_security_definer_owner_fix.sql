-- SECURITY: Ensure SECURITY DEFINER helpers are owned by the non-BYPASSRLS app role
-- This forward-only migration corrects ownership on existing functions.

set check_function_bodies = off;

-- Helper to safely alter function owner only when it exists
do $$
begin
  -- next_attempt_nr(uuid, uuid, text)
  if to_regprocedure('public.next_attempt_nr(uuid, uuid, text)') is not null then
    alter function public.next_attempt_nr(uuid, uuid, text) owner to gustav_limited;
    grant execute on function public.next_attempt_nr(uuid, uuid, text) to gustav_limited;
  end if;

  -- check_task_visible_to_student(text, uuid, uuid)
  if to_regprocedure('public.check_task_visible_to_student(text, uuid, uuid)') is not null then
    alter function public.check_task_visible_to_student(text, uuid, uuid) owner to gustav_limited;
    grant execute on function public.check_task_visible_to_student(text, uuid, uuid) to gustav_limited;
  end if;

  -- get_released_sections_for_student(text, uuid, integer, integer)
  if to_regprocedure('public.get_released_sections_for_student(text, uuid, integer, integer)') is not null then
    alter function public.get_released_sections_for_student(text, uuid, integer, integer) owner to gustav_limited;
    grant execute on function public.get_released_sections_for_student(text, uuid, integer, integer) to gustav_limited;
  end if;

  -- get_released_materials_for_student(text, uuid, uuid)
  if to_regprocedure('public.get_released_materials_for_student(text, uuid, uuid)') is not null then
    alter function public.get_released_materials_for_student(text, uuid, uuid) owner to gustav_limited;
    grant execute on function public.get_released_materials_for_student(text, uuid, uuid) to gustav_limited;
  end if;

  -- get_released_tasks_for_student(text, uuid, uuid)
  if to_regprocedure('public.get_released_tasks_for_student(text, uuid, uuid)') is not null then
    alter function public.get_released_tasks_for_student(text, uuid, uuid) owner to gustav_limited;
    grant execute on function public.get_released_tasks_for_student(text, uuid, uuid) to gustav_limited;
  end if;

  -- get_task_metadata_for_student(text, uuid, uuid)
  if to_regprocedure('public.get_task_metadata_for_student(text, uuid, uuid)') is not null then
    alter function public.get_task_metadata_for_student(text, uuid, uuid) owner to gustav_limited;
    grant execute on function public.get_task_metadata_for_student(text, uuid, uuid) to gustav_limited;
  end if;

  -- get_course_units_for_student(text, uuid)
  if to_regprocedure('public.get_course_units_for_student(text, uuid)') is not null then
    alter function public.get_course_units_for_student(text, uuid) owner to gustav_limited;
    grant execute on function public.get_course_units_for_student(text, uuid) to gustav_limited;
  end if;

  -- get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)
  if to_regprocedure('public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer)') is not null then
    alter function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer) owner to gustav_limited;
    grant execute on function public.get_released_sections_for_student_by_unit(text, uuid, uuid, integer, integer) to gustav_limited;
  end if;
end $$;

set check_function_bodies = on;
