-- Fix column reference in publish_section_for_course function
-- The course_learning_unit_assignment table uses 'unit_id' not 'learning_unit_id'

CREATE OR REPLACE FUNCTION public.publish_section_for_course(
    p_session_id UUID,
    p_course_id UUID,
    p_section_id UUID
) 
RETURNS VOID 
LANGUAGE plpgsql 
SECURITY DEFINER 
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Get user from session
    SELECT user_id INTO v_user_id
    FROM auth_sessions
    WHERE id = p_session_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check if user is teacher for course
    IF NOT EXISTS (
        SELECT 1 FROM course_teacher 
        WHERE teacher_id = v_user_id AND course_id = p_course_id
    ) AND NOT EXISTS (
        SELECT 1 FROM course 
        WHERE id = p_course_id AND creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher not authorized for this course';
    END IF;

    -- Verify section belongs to a unit assigned to this course (FIX: use unit_id instead of learning_unit_id)
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN course_learning_unit_assignment cua ON cua.unit_id = s.unit_id
        WHERE s.id = p_section_id AND cua.course_id = p_course_id
    ) THEN
        RAISE EXCEPTION 'Section does not belong to a unit assigned to this course';
    END IF;

    -- Insert or update publish state
    INSERT INTO course_unit_section_status (
        course_id,
        section_id,
        is_published,
        published_at
    )
    VALUES (
        p_course_id,
        p_section_id,
        TRUE,
        NOW()
    )
    ON CONFLICT (course_id, section_id) 
    DO UPDATE SET
        is_published = TRUE,
        published_at = NOW();
END;
$$;