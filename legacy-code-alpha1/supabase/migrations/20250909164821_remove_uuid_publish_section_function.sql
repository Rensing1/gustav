-- Remove UUID-based publish_section_for_course function to resolve function overloading conflict
-- Keep only the TEXT-based version (correct pattern)

DROP FUNCTION IF EXISTS public.publish_section_for_course(p_session_id uuid, p_course_id uuid, p_section_id uuid);