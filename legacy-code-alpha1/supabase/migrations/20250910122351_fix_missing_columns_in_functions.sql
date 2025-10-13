-- Fix missing columns in PostgreSQL RPC functions after schema changes
-- 1. concept_explanation was removed from mastery_tasks
-- 2. is_mastery was removed from task_base (now determined by join with regular_tasks/mastery_tasks)

-- =====================================================
-- Fix 1: Update get_next_due_mastery_task to remove concept_explanation
-- =====================================================
DROP FUNCTION IF EXISTS public.get_next_due_mastery_task(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_next_due_mastery_task(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    task_id UUID,
    task_title TEXT,
    section_id UUID,
    section_title TEXT,
    unit_id UUID,
    unit_title TEXT,
    difficulty_level INTEGER,
    -- Remove concept_explanation, use solution_hints from task_base instead
    solution_hints TEXT,
    prompt TEXT,
    last_attempt TIMESTAMPTZ,
    correct_attempts INTEGER,
    total_attempts INTEGER,
    due_for_review BOOLEAN,
    review_priority NUMERIC
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
        RETURN;
    END IF;

    -- Check permissions: student must be self, teacher can see all
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN;
    END IF;

    -- Verify student is enrolled in course
    IF NOT EXISTS (
        SELECT 1 FROM course_student cs
        WHERE cs.student_id = p_student_id AND cs.course_id = p_course_id
    ) THEN
        RETURN;
    END IF;

    -- Get next due mastery task using spaced repetition logic
    RETURN QUERY
    WITH course_mastery_tasks AS (
        -- Get all mastery tasks for the course
        SELECT
            t.id as task_id,
            t.title as task_title,
            t.section_id,
            s.title as section_title,
            s.unit_id,
            lu.title as unit_title,
            mt.difficulty_level,
            t.solution_hints,  -- From task_base instead of concept_explanation
            mt.prompt
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
            -- Calculate days since last attempt
            EXTRACT(EPOCH FROM (NOW() - MAX(sub.submitted_at))) / 86400 as days_since_last
        FROM course_mastery_tasks cmt
        LEFT JOIN submission sub ON
            sub.task_id = cmt.task_id AND
            sub.student_id = p_student_id
        GROUP BY cmt.task_id
    ),
    task_priorities AS (
        -- Calculate review priority using spaced repetition formula
        SELECT
            cmt.*,
            tss.last_attempt,
            tss.correct_attempts,
            tss.total_attempts,
            CASE
                -- Never attempted
                WHEN tss.total_attempts = 0 THEN TRUE
                -- Failed last attempt
                WHEN tss.correct_attempts = 0 THEN TRUE
                -- Spaced repetition intervals: 1, 3, 7, 14, 30 days
                WHEN tss.correct_attempts = 1 AND tss.days_since_last >= 1 THEN TRUE
                WHEN tss.correct_attempts = 2 AND tss.days_since_last >= 3 THEN TRUE
                WHEN tss.correct_attempts = 3 AND tss.days_since_last >= 7 THEN TRUE
                WHEN tss.correct_attempts = 4 AND tss.days_since_last >= 14 THEN TRUE
                WHEN tss.correct_attempts >= 5 AND tss.days_since_last >= 30 THEN TRUE
                ELSE FALSE
            END as due_for_review,
            -- Priority score (higher = more urgent)
            CASE
                WHEN tss.total_attempts = 0 THEN 1000  -- New tasks highest priority
                WHEN tss.correct_attempts = 0 THEN 900 -- Failed tasks high priority
                ELSE
                    -- Based on days overdue for review
                    CASE tss.correct_attempts
                        WHEN 1 THEN GREATEST(0, tss.days_since_last - 1) * 100
                        WHEN 2 THEN GREATEST(0, tss.days_since_last - 3) * 80
                        WHEN 3 THEN GREATEST(0, tss.days_since_last - 7) * 60
                        WHEN 4 THEN GREATEST(0, tss.days_since_last - 14) * 40
                        ELSE GREATEST(0, tss.days_since_last - 30) * 20
                    END
            END as review_priority
        FROM course_mastery_tasks cmt
        JOIN task_submission_stats tss ON tss.task_id = cmt.task_id
    )
    SELECT
        tp.task_id,
        tp.task_title,
        tp.section_id,
        tp.section_title,
        tp.unit_id,
        tp.unit_title,
        tp.difficulty_level,
        tp.solution_hints,
        tp.prompt,
        tp.last_attempt,
        tp.correct_attempts,
        tp.total_attempts,
        tp.due_for_review,
        tp.review_priority
    FROM task_priorities tp
    WHERE tp.due_for_review = TRUE
    ORDER BY tp.review_priority DESC, tp.difficulty_level ASC
    LIMIT 1;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_next_due_mastery_task(TEXT, UUID, UUID) TO anon;

-- =====================================================
-- Fix 2: Update get_tasks_for_section to remove is_mastery column reference
-- =====================================================
DROP FUNCTION IF EXISTS public.get_tasks_for_section(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    instruction TEXT,
    task_type TEXT,
    criteria TEXT,
    assessment_criteria JSONB,
    solution_hints TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    order_in_section INTEGER,
    is_mastery BOOLEAN,  -- Calculated from join
    max_attempts INTEGER,
    prompt TEXT,
    difficulty_level INTEGER,
    spaced_repetition_interval INTEGER
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
        RETURN;
    END IF;

    -- Check if user has access to section
    IF v_user_role = 'teacher' THEN
        -- Teacher must be creator of the unit
        IF NOT EXISTS (
            SELECT 1 
            FROM unit_section s
            JOIN learning_unit u ON u.id = s.unit_id
            WHERE s.id = p_section_id AND u.creator_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSE
        -- Students cannot manage tasks
        RETURN;
    END IF;

    -- Return tasks with proper type determination
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.instruction,
        t.task_type,
        t.criteria,
        t.assessment_criteria,
        t.solution_hints,
        t.created_at,
        t.updated_at,
        t.order_in_section,
        -- Determine if mastery based on join
        CASE WHEN mt.task_id IS NOT NULL THEN TRUE ELSE FALSE END as is_mastery,
        rt.max_attempts,
        mt.prompt,
        mt.difficulty_level,
        mt.spaced_repetition_interval
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_tasks_for_section(TEXT, UUID) TO anon;

-- =====================================================
-- Fix 3: Update get_section_tasks to remove is_mastery column reference
-- =====================================================
DROP FUNCTION IF EXISTS public.get_section_tasks(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.get_section_tasks(
    p_session_id TEXT,
    p_unit_id UUID,
    p_section_id UUID
)
RETURNS TABLE (
    task_id UUID,
    title TEXT,
    is_mastery BOOLEAN,
    order_in_section INTEGER
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
        RETURN;
    END IF;

    -- Check if user has access to unit
    IF v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM learning_unit WHERE id = p_unit_id AND creator_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSE
        RETURN;
    END IF;

    -- Return tasks for section
    RETURN QUERY
    SELECT 
        t.id as task_id,
        t.title,
        -- Determine type from join
        CASE WHEN mt.task_id IS NOT NULL THEN TRUE ELSE FALSE END as is_mastery,
        t.order_in_section
    FROM task_base t
    LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) TO anon;

-- =====================================================
-- Fix 4: Update get_mastery_tasks_for_section to not select concept_explanation
-- =====================================================
DROP FUNCTION IF EXISTS public.get_mastery_tasks_for_section(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_section(
    p_session_id TEXT,
    p_section_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id UUID,
    title TEXT,
    instruction TEXT,
    task_type TEXT,
    criteria TEXT,
    assessment_criteria JSONB,
    solution_hints TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    order_in_section INTEGER,
    prompt TEXT,
    difficulty_level INTEGER,
    spaced_repetition_interval INTEGER
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
        RETURN;
    END IF;

    -- Check authorization
    IF v_user_role = 'teacher' THEN
        -- Teacher must be creator of the unit
        IF NOT EXISTS (
            SELECT 1 
            FROM unit_section s
            JOIN learning_unit u ON u.id = s.unit_id
            WHERE s.id = p_section_id AND u.creator_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    ELSE
        -- Students cannot manage tasks
        RETURN;
    END IF;

    -- Return mastery tasks
    RETURN QUERY
    SELECT 
        t.id,
        t.section_id,
        t.title,
        t.instruction,
        t.task_type,
        t.criteria,
        t.assessment_criteria,
        t.solution_hints,
        t.created_at,
        t.updated_at,
        t.order_in_section,
        mt.prompt,
        mt.difficulty_level,
        mt.spaced_repetition_interval
    FROM task_base t
    JOIN mastery_tasks mt ON mt.task_id = t.id
    WHERE t.section_id = p_section_id
    ORDER BY t.order_in_section;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_mastery_tasks_for_section(TEXT, UUID) TO anon;

-- =====================================================
-- Fix 5: Update get_published_section_details_for_student
-- =====================================================
-- Find and fix the function that uses concept_explanation in task details
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.get_published_section_details_for_student(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    order_in_unit INTEGER,
    materials JSON,
    tasks JSON
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
        RETURN;
    END IF;

    -- Check if student is enrolled in course
    IF v_user_role = 'student' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_student
            WHERE course_id = p_course_id AND student_id = v_user_id
        ) THEN
            RETURN;
        END IF;
    END IF;

    -- Return published sections with tasks
    RETURN QUERY
    WITH published_sections AS (
        SELECT 
            s.id,
            s.title,
            s.order_in_unit,
            s.materials,
            sp.published_at
        FROM unit_section s
        JOIN section_publishing sp ON s.id = sp.section_id
        JOIN learning_unit u ON s.unit_id = u.id
        JOIN course_learning_unit_assignment cua ON u.id = cua.unit_id
        WHERE cua.course_id = p_course_id AND sp.course_id = p_course_id
    )
    SELECT 
        ps.id,
        ps.title,
        ps.order_in_unit,
        ps.materials::json,
        COALESCE(
            (SELECT json_agg(
                json_build_object(
                    'id', t.id,
                    'title', t.title,
                    'instruction', t.instruction,
                    'task_type', t.task_type,
                    'is_mastery', CASE WHEN mt.task_id IS NOT NULL THEN TRUE ELSE FALSE END,
                    'max_attempts', rt.max_attempts,
                    'prompt', mt.prompt,
                    'difficulty_level', mt.difficulty_level,
                    'solution_hints', t.solution_hints  -- Use solution_hints instead of concept_explanation
                )
                ORDER BY t.order_in_section
            )
            FROM task_base t
            LEFT JOIN regular_tasks rt ON rt.task_id = t.id
            LEFT JOIN mastery_tasks mt ON mt.task_id = t.id
            WHERE t.section_id = ps.id
            ), '[]'::json
        ) as tasks
    FROM published_sections ps
    ORDER BY ps.order_in_unit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_published_section_details_for_student(TEXT, UUID) TO anon;

-- =====================================================
-- Fix 6: Update create_mastery_task to remove concept_explanation parameter
-- =====================================================
DROP FUNCTION IF EXISTS public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER, TEXT);

CREATE OR REPLACE FUNCTION public.create_mastery_task(
    p_session_id TEXT,
    p_section_id UUID,
    p_title TEXT,
    p_instruction TEXT,
    p_task_type TEXT,
    p_assessment_criteria JSONB,
    p_solution_hints TEXT,
    p_difficulty_level INTEGER,
    p_prompt TEXT DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_task_id UUID;
    v_next_order INTEGER;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized';
    END IF;

    -- Check if teacher owns the unit
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit u ON u.id = s.unit_id
        WHERE s.id = p_section_id AND u.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized - not owner of unit';
    END IF;

    -- Get next order
    SELECT COALESCE(MAX(order_in_section), 0) + 1
    INTO v_next_order
    FROM task_base
    WHERE section_id = p_section_id;

    -- Create task in task_base
    INSERT INTO task_base (
        section_id,
        title,
        instruction,
        task_type,
        assessment_criteria,
        solution_hints,
        order_in_section
    ) VALUES (
        p_section_id,
        p_title,
        p_instruction,
        p_task_type,
        p_assessment_criteria,
        p_solution_hints,
        v_next_order
    ) RETURNING id INTO v_task_id;

    -- Create mastery task entry
    INSERT INTO mastery_tasks (
        task_id,
        prompt,
        difficulty_level,
        spaced_repetition_interval
    ) VALUES (
        v_task_id,
        p_prompt,
        p_difficulty_level,
        1  -- Default interval
    );

    RETURN v_task_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER, TEXT) TO anon;

-- =====================================================
-- Fix 7: Fix calculate_learning_streak function
-- =====================================================
DROP FUNCTION IF EXISTS public.calculate_learning_streak(TEXT, UUID);

CREATE OR REPLACE FUNCTION public.calculate_learning_streak(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS INTEGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_streak INTEGER DEFAULT 0;
    v_last_date DATE;
    v_current_date DATE;
    v_submission_date DATE;
    v_submission_record RECORD;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN 0;
    END IF;

    -- Check permissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RETURN 0;
    END IF;

    -- Get submissions in reverse chronological order
    FOR v_submission_record IN
        SELECT DISTINCT DATE(submitted_at AT TIME ZONE 'Europe/Berlin') as submission_date
        FROM submission
        WHERE student_id = p_student_id
            AND is_correct = true
        ORDER BY submission_date DESC
    LOOP
        v_submission_date := v_submission_record.submission_date;
        
        -- First iteration
        IF v_last_date IS NULL THEN
            v_last_date := v_submission_date;
            v_current_date := CURRENT_DATE AT TIME ZONE 'Europe/Berlin';
            
            -- Check if streak is still active (submission today or yesterday)
            IF v_submission_date >= v_current_date - INTERVAL '1 day' THEN
                v_streak := 1;
            ELSE
                -- Streak is broken
                RETURN 0;
            END IF;
        ELSE
            -- Check if this date continues the streak
            IF v_submission_date = v_last_date - INTERVAL '1 day' THEN
                v_streak := v_streak + 1;
                v_last_date := v_submission_date;
            ELSE
                -- Streak is broken
                EXIT;
            END IF;
        END IF;
    END LOOP;

    RETURN v_streak;
END;
$$;

GRANT EXECUTE ON FUNCTION public.calculate_learning_streak(TEXT, UUID) TO anon;

-- =====================================================
-- Comment on changes
-- =====================================================
COMMENT ON FUNCTION public.get_next_due_mastery_task(TEXT, UUID, UUID) IS 'Returns next due mastery task. Uses solution_hints from task_base instead of removed concept_explanation column';
COMMENT ON FUNCTION public.get_tasks_for_section(TEXT, UUID) IS 'Returns all tasks in section. is_mastery determined by join with mastery_tasks table';
COMMENT ON FUNCTION public.get_section_tasks(TEXT, UUID, UUID) IS 'Returns task list for section. is_mastery determined by join with mastery_tasks table';
COMMENT ON FUNCTION public.create_mastery_task(TEXT, UUID, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER, TEXT) IS 'Creates mastery task. concept_explanation parameter removed - use solution_hints instead';
COMMENT ON FUNCTION public.calculate_learning_streak(TEXT, UUID) IS 'Calculate learning streak for student. Fixed unpacking error.';