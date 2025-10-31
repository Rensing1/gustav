-- Ensure EXECUTE privileges for learning student RLS helper functions are explicit
-- and limited to the application role (gustav_limited). This avoids reliance on
-- default PUBLIC permissions and makes privilege intent auditable.

set search_path = public, pg_temp;

-- Helper: student_is_course_member(p_student_sub text, p_course_id uuid)
revoke all on function public.student_is_course_member(text, uuid) from public;
grant execute on function public.student_is_course_member(text, uuid) to gustav_limited;

-- Helper: student_can_access_unit(p_student_sub text, p_unit_id uuid)
revoke all on function public.student_can_access_unit(text, uuid) from public;
grant execute on function public.student_can_access_unit(text, uuid) to gustav_limited;

-- Helper: student_can_access_course_module(p_student_sub text, p_course_module_id uuid)
revoke all on function public.student_can_access_course_module(text, uuid) from public;
grant execute on function public.student_can_access_course_module(text, uuid) to gustav_limited;

-- Helper: student_can_access_section(p_student_sub text, p_section_id uuid)
revoke all on function public.student_can_access_section(text, uuid) from public;
grant execute on function public.student_can_access_section(text, uuid) to gustav_limited;

