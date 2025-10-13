-- Remove old version of get_published_section_details_for_student function with section_description
-- Keep only the version without the non-existent description column

DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(p_session_id text, p_student_id uuid, p_unit_id uuid, p_course_id uuid);