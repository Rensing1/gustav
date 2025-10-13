-- Remove redundant title column from task_base
-- Analysis showed that title is almost always identical to instruction
-- The few differences are just test data with " - Updated" suffix

-- First, we need to update all functions that reference title column
-- This must be done BEFORE dropping the column

-- =====================================================
-- Update get_next_due_mastery_task to not use title
-- =====================================================
DROP FUNCTION IF EXISTS public.get_next_due_mastery_task(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_next_due_mastery_task(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    task_id UUID,
    instruction TEXT,
    difficulty_level INTEGER,
    solution_hints TEXT,
    section_id UUID,
    section_title TEXT,
    unit_id UUID,
    unit_title TEXT,
    total_attempts INTEGER,
    correct_attempts INTEGER,
    days_since_last_attempt INTEGER,
    priority_score NUMERIC
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
    
    IF NOT v_is_valid OR v_auth_user_id IS NULL OR v_auth_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Get next due mastery task using spaced repetition logic
    RETURN QUERY
    WITH course_mastery_tasks AS (
        -- Get all mastery tasks for the course
        SELECT
            t.id as task_id,
            t.section_id,
            s.title as section_title,
            s.unit_id,
            lu.title as unit_title,
            mt.difficulty_level,
            t.solution_hints,
            t.instruction
        FROM task_base t
        JOIN mastery_tasks mt ON mt.task_id = t.id
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id
        JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id
        WHERE cua.course_id = p_course_id
    ),
    task_submission_stats AS (
        -- Get submission statistics for each task
        SELECT
            cmt.task_id,
            COUNT(sub.id) as total_attempts,
            COUNT(CASE WHEN sub.is_correct THEN 1 END) as correct_attempts,
            MAX(sub.submitted_at) as last_attempt,
            -- Calculate days since last attempt, default to very high if never attempted
            COALESCE(
                EXTRACT(EPOCH FROM (NOW() - MAX(sub.submitted_at))) / 86400.0,
                999999
            )::INTEGER as days_since_last
        FROM course_mastery_tasks cmt
        LEFT JOIN submission sub ON sub.task_id = cmt.task_id 
            AND sub.student_id = p_student_id
        GROUP BY cmt.task_id
    ),
    prioritized_tasks AS (
        -- Calculate priority score for each task
        SELECT
            cmt.*,
            tss.total_attempts::INTEGER,
            tss.correct_attempts::INTEGER,
            tss.days_since_last,
            -- Priority score calculation
            CASE
                -- Never attempted: highest priority (1000 + difficulty bonus)
                WHEN tss.total_attempts = 0 THEN 1000.0 + (cmt.difficulty_level * 10.0)
                -- Tasks with no correct attempts: high priority based on days
                WHEN tss.correct_attempts = 0 THEN 
                    500.0 + (tss.days_since_last * 10.0) + (cmt.difficulty_level * 5.0)
                -- Tasks with correct attempts: spaced repetition
                ELSE 
                    -- Base score from days since last attempt
                    (tss.days_since_last * 5.0)
                    -- Adjust by success rate (lower success = higher priority)
                    * (2.0 - (tss.correct_attempts::NUMERIC / NULLIF(tss.total_attempts, 0)::NUMERIC))
                    -- Adjust by difficulty
                    * (1.0 + (cmt.difficulty_level * 0.1))
            END as priority_score
        FROM course_mastery_tasks cmt
        JOIN task_submission_stats tss ON tss.task_id = cmt.task_id
    ),
    filtered_tasks AS (
        -- Filter out tasks that are too recent or have been mastered
        SELECT *
        FROM prioritized_tasks pt
        WHERE 
            -- Include if never attempted
            pt.total_attempts = 0
            -- Or if no correct attempts yet
            OR pt.correct_attempts = 0
            -- Or if enough time has passed based on spaced repetition
            OR pt.days_since_last >= CASE
                WHEN pt.correct_attempts = 1 THEN 1   -- 1 day after first correct
                WHEN pt.correct_attempts = 2 THEN 3   -- 3 days after second correct
                WHEN pt.correct_attempts = 3 THEN 7   -- 7 days after third correct
                WHEN pt.correct_attempts = 4 THEN 14  -- 14 days after fourth correct
                ELSE 30  -- 30 days for well-mastered tasks
            END
    )
    -- Return the highest priority task
    SELECT
        ft.task_id,
        ft.instruction,
        ft.difficulty_level,
        ft.solution_hints,
        ft.section_id,
        ft.section_title,
        ft.unit_id,
        ft.unit_title,
        ft.total_attempts,
        ft.correct_attempts,
        ft.days_since_last as days_since_last_attempt,
        ROUND(ft.priority_score, 2) as priority_score
    FROM filtered_tasks ft
    ORDER BY ft.priority_score DESC
    LIMIT 1;
END;
$$;

-- =====================================================
-- Update get_tasks_for_section to not use title
-- =====================================================
DROP FUNCTION IF EXISTS public.get_tasks_for_section(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE(
    task_id UUID,
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
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        t.solution_hints,
        mt.difficulty_level,
        rt.max_attempts,
        t.order_in_section
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

-- =====================================================
-- Update get_mastery_tasks_for_section to not use title
-- =====================================================
DROP FUNCTION IF EXISTS public.get_mastery_tasks_for_section(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE(
    task_id UUID,
    instruction TEXT,
    task_type TEXT,
    solution_hints TEXT,
    order_in_section INTEGER,
    difficulty_level INTEGER,
    spaced_repetition_interval INTEGER
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

    -- Return only mastery tasks for the section
    RETURN QUERY
    SELECT
        t.id as task_id,
        t.instruction,
        t.task_type,
        t.solution_hints,
        t.order_in_section,
        mt.difficulty_level,
        mt.spaced_repetition_interval
    FROM task_base t
    JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

-- =====================================================
-- Update get_section_tasks to not use title
-- =====================================================
DROP FUNCTION IF EXISTS public.get_section_tasks(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_section_tasks(
    p_session_id TEXT,
    p_section_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    id UUID,
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

-- =====================================================
-- Update get_task_details to not use title
-- =====================================================
DROP FUNCTION IF EXISTS public.get_task_details(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_task_details(
    p_session_id TEXT,
    p_task_id UUID
)
RETURNS TABLE(
    id UUID,
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
        t.instruction,
        t.task_type,
        CASE WHEN mt.task_id IS NOT NULL THEN true ELSE false END as is_mastery,
        rt.max_attempts,
        mt.difficulty_level,
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

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_next_due_mastery_task(TEXT, UUID, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_tasks_for_section(TEXT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_mastery_tasks_for_section(TEXT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) TO anon;
GRANT EXECUTE ON FUNCTION public.get_task_details(TEXT, UUID) TO anon;

-- Drop views that depend on title column
DROP VIEW IF EXISTS all_regular_tasks;
DROP VIEW IF EXISTS all_mastery_tasks;

-- Now we can safely drop the title column
ALTER TABLE task_base DROP COLUMN title;

-- Recreate views without title column
CREATE OR REPLACE VIEW all_regular_tasks AS
SELECT 
    t.id,
    t.section_id,
    t.instruction,
    t.task_type,
    t.order_in_section,
    t.created_at,
    t.updated_at,
    t.criteria,
    t.assessment_criteria,
    t.solution_hints,
    rt.prompt,
    rt.max_attempts,
    rt.grading_criteria,
    false as is_mastery
FROM task_base t
JOIN regular_tasks rt ON rt.task_id = t.id;

CREATE OR REPLACE VIEW all_mastery_tasks AS
SELECT 
    t.id,
    t.section_id,
    t.instruction,
    t.task_type,
    t.order_in_section,
    t.created_at,
    t.updated_at,
    t.criteria,
    t.assessment_criteria,
    t.solution_hints,
    mt.difficulty_level,
    mt.spaced_repetition_interval,
    true as is_mastery
FROM task_base t
JOIN mastery_tasks mt ON mt.task_id = t.id;

-- Update comments
COMMENT ON FUNCTION public.get_next_due_mastery_task(TEXT, UUID, UUID) IS 'Returns next mastery task. No longer uses redundant title column';
COMMENT ON FUNCTION public.get_tasks_for_section(TEXT, UUID) IS 'Returns tasks without title column';
COMMENT ON FUNCTION public.get_mastery_tasks_for_section(TEXT, UUID) IS 'Returns mastery tasks without title column';
COMMENT ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) IS 'Returns section tasks without title column';
COMMENT ON FUNCTION public.get_task_details(TEXT, UUID) IS 'Returns task details without title column';
COMMENT ON COLUMN task_base.instruction IS 'The main text/prompt of the task. This is what the student sees';