-- Remove old text-based publish_section_for_course function to resolve function overloading conflict
-- Keep only the UUID-based version

DROP FUNCTION IF EXISTS public.publish_section_for_course(p_session_id text, p_section_id uuid, p_course_id uuid);