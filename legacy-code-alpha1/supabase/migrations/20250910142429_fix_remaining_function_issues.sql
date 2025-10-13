-- Fix remaining function issues after HttpOnly cookie migration

-- 1. Fix update_task_in_new_structure - change title to instruction
CREATE OR REPLACE FUNCTION public.update_task_in_new_structure(
    p_session_id TEXT,
    p_task_id UUID,
    p_title TEXT,
    p_prompt TEXT,
    p_task_type TEXT,
    p_order_in_section INT DEFAULT NULL,
    p_max_attempts INT DEFAULT NULL,
    p_grading_criteria TEXT[] DEFAULT NULL,
    p_difficulty_level INT DEFAULT NULL,
    p_concept_explanation TEXT DEFAULT NULL
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_is_regular BOOLEAN;
    v_is_mastery BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can update tasks';
    END IF;

    -- Check if teacher has access to the task
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id
        WHERE t.id = p_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Detect task type
    SELECT EXISTS(SELECT 1 FROM regular_tasks WHERE task_id = p_task_id) INTO v_is_regular;
    SELECT EXISTS(SELECT 1 FROM mastery_tasks WHERE task_id = p_task_id) INTO v_is_mastery;

    IF NOT v_is_regular AND NOT v_is_mastery THEN
        RAISE EXCEPTION 'Task not found in either regular_tasks or mastery_tasks';
    END IF;

    -- Update task_base (changed title to instruction)
    UPDATE task_base
    SET 
        instruction = p_title,  -- Changed from title to instruction
        task_type = p_task_type,
        order_in_section = CASE 
            WHEN v_is_regular THEN COALESCE(p_order_in_section, order_in_section)
            ELSE order_in_section -- Mastery tasks don't have order
        END
    WHERE id = p_task_id;

    -- Update type-specific table
    IF v_is_regular THEN
        UPDATE regular_tasks
        SET 
            prompt = p_prompt,
            max_attempts = COALESCE(p_max_attempts, max_attempts),
            grading_criteria = COALESCE(p_grading_criteria, grading_criteria)
        WHERE task_id = p_task_id;
    ELSE
        UPDATE mastery_tasks
        SET 
            prompt = p_prompt,
            difficulty_level = COALESCE(p_difficulty_level, difficulty_level),
            concept_explanation = COALESCE(p_concept_explanation, concept_explanation)
        WHERE task_id = p_task_id;
    END IF;
END;
$$;

-- 2. Fix get_section_tasks to return instruction as title (for backward compatibility)
DROP FUNCTION IF EXISTS public.get_section_tasks(TEXT, UUID, UUID);

CREATE FUNCTION public.get_section_tasks(
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
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_auth_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Return task list
    RETURN QUERY
    SELECT 
        t.id,
        t.instruction::TEXT as title,  -- Return instruction as title for backward compatibility
        t.instruction,
        t.task_type,
        t.order_in_section,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts::INTEGER,
        mt.difficulty_level,
        t.solution_hints
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) TO anon;

-- 3. Fix delete_task_in_new_structure - remove learning_unit_id reference
DROP FUNCTION IF EXISTS public.delete_task_in_new_structure(TEXT, UUID);

CREATE FUNCTION public.delete_task_in_new_structure(
    p_session_id TEXT,
    p_task_id UUID
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
        RAISE EXCEPTION 'Unauthorized: Only teachers can delete tasks';
    END IF;

    -- Check if teacher has access to the task
    IF NOT EXISTS (
        SELECT 1 
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id  -- Changed from s.learning_unit_id
        WHERE t.id = p_task_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own the learning unit';
    END IF;

    -- Delete from type-specific table first (due to foreign key constraints)
    DELETE FROM regular_tasks WHERE task_id = p_task_id;
    DELETE FROM mastery_tasks WHERE task_id = p_task_id;
    
    -- Then delete from base table
    DELETE FROM task_base WHERE id = p_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.delete_task_in_new_structure(TEXT, UUID) TO anon;

-- 4. Fix calculate_learning_streak - proper return type
DROP FUNCTION IF EXISTS public.calculate_learning_streak(TEXT, UUID);

CREATE FUNCTION public.calculate_learning_streak(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS TABLE(
    current_streak INTEGER,
    longest_streak INTEGER,
    last_activity_date DATE
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
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized access to student data';
    END IF;
    
    -- Calculate streaks
    RETURN QUERY
    WITH daily_submissions AS (
        SELECT DISTINCT DATE(timestamp) as submission_date
        FROM submission
        WHERE student_id = p_student_id
        ORDER BY submission_date DESC
    ),
    streak_groups AS (
        SELECT 
            submission_date,
            submission_date - INTERVAL '1 day' * ROW_NUMBER() OVER (ORDER BY submission_date DESC) as streak_group
        FROM daily_submissions
    ),
    streaks AS (
        SELECT 
            streak_group,
            COUNT(*) as streak_length,
            MAX(submission_date) as streak_end,
            MIN(submission_date) as streak_start
        FROM streak_groups
        GROUP BY streak_group
    ),
    current_streak_calc AS (
        SELECT 
            CASE 
                WHEN MAX(streak_end) >= CURRENT_DATE - INTERVAL '1 day' 
                THEN MAX(streak_length) 
                ELSE 0 
            END as current_streak
        FROM streaks
        WHERE streak_end >= CURRENT_DATE - INTERVAL '1 day'
    ),
    longest_streak_calc AS (
        SELECT COALESCE(MAX(streak_length), 0) as longest_streak
        FROM streaks
    ),
    last_activity AS (
        SELECT COALESCE(MAX(submission_date), CURRENT_DATE) as last_date
        FROM daily_submissions
    )
    SELECT 
        COALESCE(cs.current_streak, 0)::INTEGER as current_streak,
        COALESCE(ls.longest_streak, 0)::INTEGER as longest_streak,
        la.last_date as last_activity_date
    FROM current_streak_calc cs
    CROSS JOIN longest_streak_calc ls
    CROSS JOIN last_activity la;
END;
$$;

GRANT EXECUTE ON FUNCTION public.calculate_learning_streak(TEXT, UUID) TO anon;