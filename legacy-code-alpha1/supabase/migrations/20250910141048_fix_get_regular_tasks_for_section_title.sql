-- Fix get_regular_tasks_for_section to use instruction instead of title

-- Drop the existing function first (cannot change return type)
DROP FUNCTION IF EXISTS public.get_regular_tasks_for_section(TEXT, UUID);

-- Recreate get_regular_tasks_for_section to use instruction instead of title
CREATE FUNCTION public.get_regular_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    instruction TEXT,  -- Changed from title to instruction
    task_type TEXT,
    order_in_section INT,
    created_at TIMESTAMPTZ,
    prompt TEXT,
    max_attempts INT,
    grading_criteria TEXT[]
)
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
    
    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Invalid session';
    END IF;
    
    -- Check authorization based on role
    IF v_user_role = 'teacher' THEN
        -- Teacher must own the learning unit
        IF NOT EXISTS (
            SELECT 1 
            FROM unit_section s
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE s.id = p_section_id AND lu.creator_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Student must be enrolled in a course with this section published
        IF NOT EXISTS (
            SELECT 1 
            FROM unit_section s
            JOIN course_unit_section_status cuss ON cuss.section_id = s.id
            JOIN course_students cs ON cs.course_id = cuss.course_id
            WHERE s.id = p_section_id 
            AND cs.student_id = v_user_id 
            AND cuss.is_published = TRUE
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Section not accessible to student';
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid user role';
    END IF;
    
    -- Return regular tasks for the section
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.instruction,  -- Use instruction instead of title
        t.task_type,
        t.order_in_section,
        t.created_at,
        t.prompt,
        t.max_attempts,
        t.grading_criteria
    FROM all_regular_tasks t
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;