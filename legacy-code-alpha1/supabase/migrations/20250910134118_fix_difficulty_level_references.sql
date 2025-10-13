-- Fix references to rt.difficulty_level which doesn't exist
-- Regular tasks don't have difficulty_level, only mastery tasks do

-- =====================================================
-- Fix 1: get_tasks_for_section
-- =====================================================
DROP FUNCTION IF EXISTS public.get_tasks_for_section(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE(
    task_id UUID,
    title TEXT,
    instruction TEXT,
    task_type TEXT,
    is_mastery BOOLEAN,
    solution_hints TEXT,
    difficulty_level INTEGER,
    max_attempts INTEGER,
    order_in_section INTEGER
)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role user_role;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, CAST(user_role AS user_role), is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teachers must own the learning unit
        IF NOT EXISTS (
            SELECT 1
            FROM unit_section s
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE s.id = p_section_id AND lu.creator_id = v_auth_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Not the owner of this unit';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unauthorized: Invalid role';
    END IF;

    -- Return all tasks for the section
    RETURN QUERY
    SELECT
        t.id as task_id,
        t.title,
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        t.solution_hints,
        mt.difficulty_level,  -- Only mastery tasks have difficulty_level
        rt.max_attempts,
        t.order_in_section
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_tasks_for_section(TEXT, UUID) TO anon;

-- =====================================================
-- Fix 2: get_section_tasks
-- =====================================================
DROP FUNCTION IF EXISTS public.get_section_tasks(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_section_tasks(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    id UUID,
    title TEXT,
    instruction TEXT,
    task_type TEXT,
    order_in_section INTEGER,
    is_mastery BOOLEAN,
    max_attempts INTEGER,
    difficulty_level INTEGER,
    solution_hints TEXT
) 
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role user_role;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, CAST(user_role AS user_role), is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Return task list based on role
    RETURN QUERY
    SELECT 
        t.id,
        t.title,
        t.instruction,
        t.task_type,
        t.order_in_section,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts::INTEGER,
        mt.difficulty_level,  -- Only mastery tasks have difficulty_level
        t.solution_hints
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) TO anon;

-- =====================================================
-- Fix 3: get_task_details
-- =====================================================
DROP FUNCTION IF EXISTS public.get_task_details(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_task_details(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS TABLE(
    id UUID,
    title TEXT,
    instruction TEXT,
    task_type TEXT,
    is_mastery BOOLEAN,
    max_attempts INTEGER,
    difficulty_level INTEGER,
    solution_hints TEXT
)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
    v_auth_user_id UUID;
    v_user_role user_role;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, CAST(user_role AS user_role), is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Return task details
    RETURN QUERY
    SELECT
        t.id,
        t.title,
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts,
        mt.difficulty_level,  -- Only mastery tasks have difficulty_level
        t.solution_hints
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.id = p_task_id;

    -- Additional authorization check based on role
    IF v_user_role = 'teacher' THEN
        -- Teachers must own the unit
        IF NOT EXISTS (
            SELECT 1
            FROM task_base t
            JOIN unit_section s ON s.id = t.section_id
            JOIN learning_unit lu ON lu.id = s.unit_id
            WHERE t.id = p_task_id AND lu.creator_id = v_auth_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Not the owner of this task';
        END IF;
    ELSIF v_user_role = 'student' THEN
        -- Students must have access to the published section
        IF NOT EXISTS (
            SELECT 1
            FROM task_base t
            JOIN unit_section s ON s.id = t.section_id
            JOIN course_section_publication csp ON csp.section_id = s.id
            JOIN course_enrollment ce ON ce.course_id = csp.course_id
            WHERE t.id = p_task_id 
            AND ce.student_id = v_auth_user_id
            AND csp.is_published = true
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Task not accessible';
        END IF;
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_task_details(TEXT, UUID) TO anon;

-- Comment on changes
COMMENT ON FUNCTION public.get_tasks_for_section(TEXT, UUID) IS 'Fixed: Only mastery tasks have difficulty_level, not regular tasks';
COMMENT ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) IS 'Fixed: Only mastery tasks have difficulty_level, not regular tasks';
COMMENT ON FUNCTION public.get_task_details(TEXT, UUID) IS 'Fixed: Only mastery tasks have difficulty_level, not regular tasks';