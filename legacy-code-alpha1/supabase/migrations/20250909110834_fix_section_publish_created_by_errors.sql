-- Fix created_by references in section publish/unpublish functions
-- Problem: Functions still reference created_by instead of creator_id

BEGIN;

-- Fix publish_section_for_course
CREATE OR REPLACE FUNCTION public.publish_section_for_course(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can publish sections';
    END IF;

    -- Check teacher authorization - FIX: Use creator_id instead of created_by
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Insert or update section status to published
    INSERT INTO course_unit_section_status (course_id, section_id, is_published, published_at)
    VALUES (p_course_id, p_section_id, TRUE, NOW())
    ON CONFLICT (course_id, section_id) 
    DO UPDATE SET is_published = TRUE, published_at = NOW();
END;
$$;

-- Fix unpublish_section_for_course  
CREATE OR REPLACE FUNCTION public.unpublish_section_for_course(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can unpublish sections';
    END IF;

    -- Check teacher authorization - FIX: Use creator_id instead of created_by
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Update section status to unpublished
    INSERT INTO course_unit_section_status (course_id, section_id, is_published, unpublished_at)
    VALUES (p_course_id, p_section_id, FALSE, NOW())
    ON CONFLICT (course_id, section_id) 
    DO UPDATE SET is_published = FALSE, unpublished_at = NOW();
END;
$$;

COMMIT;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.publish_section_for_course TO anon;
GRANT EXECUTE ON FUNCTION public.unpublish_section_for_course TO anon;