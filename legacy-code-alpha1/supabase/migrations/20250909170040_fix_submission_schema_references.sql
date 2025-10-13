-- Comprehensive fix for submission schema references after HttpOnly cookie migration
-- Issues addressed:
-- 1. s.learning_unit_id -> s.unit_id in unit_section table
-- 2. s.submission_text -> s.submission_data in submission table  
-- 3. mastery_task -> mastery_tasks table name
-- 4. feedback.page_identifier -> this column doesn't exist

-- First, let's fix all remaining s.learning_unit_id references in functions

-- Drop and recreate functions to avoid return type conflicts
DROP FUNCTION IF EXISTS public.get_submissions_for_course_and_unit(TEXT, UUID, UUID);
DROP FUNCTION IF EXISTS public.get_submission_history(TEXT, UUID, UUID);
DROP FUNCTION IF EXISTS public.get_submission_for_task(TEXT, UUID, UUID);
DROP FUNCTION IF EXISTS public.create_submission(TEXT, UUID, JSONB);
DROP FUNCTION IF EXISTS public.move_task_up(TEXT, UUID);
DROP FUNCTION IF EXISTS public.move_task_down(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_next_due_mastery_task(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_mastery_tasks_for_course(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_submission_status_matrix(TEXT, UUID, UUID);

-- Fix get_submissions_for_course_and_unit
CREATE OR REPLACE FUNCTION public.get_submissions_for_course_and_unit(
    p_session_id TEXT,
    p_course_id UUID,
    p_unit_id UUID
)
RETURNS TABLE (
    student_id UUID,
    student_name TEXT,
    task_id UUID,
    task_title TEXT,
    submission_data JSONB,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    teacher_feedback TEXT,
    override_grade TEXT
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

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view submissions';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit lu
        WHERE lu.id = p_unit_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    RETURN QUERY
    SELECT 
        sub.student_id,
        p.name as student_name,
        sub.task_id,
        t.title as task_title,
        sub.submission_data,  -- FIXED: was s.submission_text
        sub.is_correct,
        sub.submitted_at,
        sub.ai_feedback,
        sub.teacher_override_feedback as teacher_feedback,
        sub.teacher_override_grade as override_grade
    FROM submission sub
    JOIN task_base t ON t.id = sub.task_id
    JOIN unit_section s ON s.id = t.section_id
    JOIN profiles p ON p.id = sub.student_id
    WHERE s.unit_id = p_unit_id  -- FIXED: was s.learning_unit_id
    AND EXISTS (
        SELECT 1 FROM course_student cs
        WHERE cs.student_id = sub.student_id 
        AND cs.course_id = p_course_id
    )
    ORDER BY p.name, t.title, sub.submitted_at DESC;
END;
$$;

-- Fix get_submission_history
CREATE OR REPLACE FUNCTION public.get_submission_history(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_data JSONB,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    grade TEXT,
    feedback_generated_at TIMESTAMPTZ,
    grade_generated_at TIMESTAMPTZ
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

    -- Permission check: student can only see their own, teacher can see any
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own submissions';
    END IF;

    RETURN QUERY
    SELECT 
        s.id,
        s.student_id,
        s.task_id,
        s.submission_data,  -- FIXED: was s.submission_text
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        s.ai_grade as grade,
        s.feedback_generated_at,
        s.grade_generated_at
    FROM submission s
    WHERE s.student_id = p_student_id 
    AND s.task_id = p_task_id
    ORDER BY s.submitted_at DESC;
END;
$$;

-- Fix get_submission_for_task 
CREATE OR REPLACE FUNCTION public.get_submission_for_task(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    submission_data JSONB,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    grade TEXT
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

    -- Permission check
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own submissions';
    END IF;

    RETURN QUERY
    SELECT 
        s.id,
        s.submission_data,  -- FIXED: was s.submission_text
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        s.ai_grade as grade
    FROM submission s
    WHERE s.student_id = p_student_id 
    AND s.task_id = p_task_id
    ORDER BY s.submitted_at DESC
    LIMIT 1;
END;
$$;

-- Fix create_submission function
CREATE OR REPLACE FUNCTION public.create_submission(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_data JSONB
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_section_id UUID;
    v_course_id UUID;
    v_max_attempts INT;
    v_current_attempts INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'student' THEN
        RAISE EXCEPTION 'Unauthorized: Only students can submit';
    END IF;

    -- Get task info and check if it exists
    SELECT t.section_id 
    INTO v_section_id
    FROM task_base t
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- Get course_id for this task (FIXED: unit_id instead of learning_unit_id)
    SELECT cua.course_id
    INTO v_course_id
    FROM unit_section s
    JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
    WHERE s.id = v_section_id
    LIMIT 1;

    -- Check if student is enrolled in the course
    IF NOT EXISTS (
        SELECT 1 FROM course_student cs 
        WHERE cs.student_id = v_user_id AND cs.course_id = v_course_id
    ) THEN
        RAISE EXCEPTION 'Student not enrolled in course';
    END IF;

    -- Get max attempts for this task
    SELECT rt.max_attempts 
    INTO v_max_attempts
    FROM regular_tasks rt
    WHERE rt.task_id = p_task_id;

    IF v_max_attempts IS NULL THEN
        v_max_attempts := 1; -- Default for mastery tasks
    END IF;

    -- Check current attempts
    SELECT COUNT(*)::INT 
    INTO v_current_attempts
    FROM submission s
    WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

    IF v_current_attempts >= v_max_attempts THEN
        RAISE EXCEPTION 'Maximum attempts exceeded for this task';
    END IF;

    -- Create submission
    INSERT INTO submission (
        student_id,
        task_id,
        submission_data,  -- FIXED: was submission_text
        attempt_number
    ) VALUES (
        v_user_id,
        p_task_id,
        p_submission_data,
        v_current_attempts + 1
    ) RETURNING id INTO v_submission_id;

    RETURN v_submission_id;
END;
$$;

-- Fix move_task_up function
CREATE OR REPLACE FUNCTION public.move_task_up(
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
    v_section_id UUID;
    v_current_order INT;
    v_swap_task_id UUID;
    v_swap_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can move tasks';
    END IF;

    -- Get current task info
    SELECT t.section_id, rt.order_in_section
    INTO v_section_id, v_current_order
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- Check if teacher owns the unit (FIXED: unit_id instead of learning_unit_id)
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
        WHERE s.id = v_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Find task to swap with (previous task)
    SELECT t.id, rt.order_in_section
    INTO v_swap_task_id, v_swap_order
    FROM task_base t
    JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.section_id = v_section_id 
    AND rt.order_in_section < v_current_order
    ORDER BY rt.order_in_section DESC
    LIMIT 1;

    IF v_swap_task_id IS NULL THEN
        RETURN; -- Already at top
    END IF;

    -- Swap orders
    UPDATE regular_tasks SET order_in_section = v_swap_order WHERE task_id = p_task_id;
    UPDATE regular_tasks SET order_in_section = v_current_order WHERE task_id = v_swap_task_id;
END;
$$;

-- Fix move_task_down function  
CREATE OR REPLACE FUNCTION public.move_task_down(
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
    v_section_id UUID;
    v_current_order INT;
    v_swap_task_id UUID;
    v_swap_order INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can move tasks';
    END IF;

    -- Get current task info
    SELECT t.section_id, rt.order_in_section
    INTO v_section_id, v_current_order
    FROM task_base t
    LEFT JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.id = p_task_id;

    IF v_section_id IS NULL THEN
        RAISE EXCEPTION 'Task not found';
    END IF;

    -- Check if teacher owns the unit (FIXED: unit_id instead of learning_unit_id) 
    IF NOT EXISTS (
        SELECT 1 
        FROM unit_section s
        JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
        WHERE s.id = v_section_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Find task to swap with (next task)
    SELECT t.id, rt.order_in_section
    INTO v_swap_task_id, v_swap_order
    FROM task_base t
    JOIN regular_tasks rt ON rt.task_id = t.id
    WHERE t.section_id = v_section_id 
    AND rt.order_in_section > v_current_order
    ORDER BY rt.order_in_section ASC
    LIMIT 1;

    IF v_swap_task_id IS NULL THEN
        RETURN; -- Already at bottom
    END IF;

    -- Swap orders
    UPDATE regular_tasks SET order_in_section = v_swap_order WHERE task_id = p_task_id;
    UPDATE regular_tasks SET order_in_section = v_current_order WHERE task_id = v_swap_task_id;
END;
$$;

-- Fix get_next_due_mastery_task function 
CREATE OR REPLACE FUNCTION public.get_next_due_mastery_task(
    p_session_id TEXT,
    p_student_id UUID
)
RETURNS TABLE (
    task_id UUID,
    title TEXT,
    instruction TEXT,
    section_title TEXT,
    unit_title TEXT,
    due_date TIMESTAMPTZ,
    days_until_due INT
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

    -- Permission check
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own tasks';
    END IF;

    RETURN QUERY
    WITH student_courses AS (
        SELECT DISTINCT cs.course_id
        FROM course_student cs 
        WHERE cs.student_id = p_student_id
    ),
    available_mastery_tasks AS (
        SELECT DISTINCT
            tb.id,
            tb.title,
            tb.instruction,
            us.title as section_title,
            lu.title as unit_title,
            ml.next_due as due_date,
            EXTRACT(days FROM (ml.next_due - NOW()))::INT as days_until_due
        FROM task_base tb
        JOIN mastery_tasks mt ON mt.task_id = tb.id
        JOIN unit_section us ON us.id = tb.section_id
        JOIN learning_unit lu ON lu.id = us.unit_id  -- FIXED: was us.learning_unit_id
        JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
        JOIN student_courses sc ON sc.course_id = cua.course_id
        LEFT JOIN mastery_log ml ON ml.student_id = p_student_id AND ml.task_id = tb.id
        WHERE (ml.next_due IS NULL OR ml.next_due <= NOW())
        ORDER BY COALESCE(ml.next_due, NOW()) ASC
    )
    SELECT 
        amt.id as task_id,
        amt.title,
        amt.instruction,
        amt.section_title,
        amt.unit_title,
        amt.due_date,
        amt.days_until_due
    FROM available_mastery_tasks amt
    LIMIT 1;
END;
$$;

-- Fix get_mastery_tasks_for_course function - change mastery_task to mastery_tasks
CREATE OR REPLACE FUNCTION public.get_mastery_tasks_for_course(
    p_session_id TEXT,
    p_course_id UUID
)
RETURNS TABLE (
    task_id UUID,
    title TEXT,
    instruction TEXT,
    section_title TEXT,
    unit_title TEXT,
    spaced_repetition_interval INT
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

    -- Check if user can access this course
    IF v_user_role = 'teacher' THEN
        -- Teachers can only view mastery tasks for courses they teach or own
        IF NOT EXISTS (
            SELECT 1 FROM course c
            WHERE c.id = p_course_id 
            AND (c.creator_id = v_user_id OR EXISTS (
                SELECT 1 FROM course_teacher ct 
                WHERE ct.course_id = c.id AND ct.teacher_id = v_user_id
            ))
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Only teachers can view mastery tasks for course';
        END IF;
    ELSE
        -- Students can only view mastery tasks for courses they're enrolled in
        IF NOT EXISTS (
            SELECT 1 FROM course_student cs 
            WHERE cs.course_id = p_course_id AND cs.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student not enrolled in this course';
        END IF;
    END IF;

    RETURN QUERY
    SELECT 
        tb.id as task_id,
        tb.title,
        tb.instruction,
        us.title as section_title,
        lu.title as unit_title,
        mt.spaced_repetition_interval
    FROM task_base tb
    JOIN mastery_tasks mt ON mt.task_id = tb.id  -- FIXED: was mastery_task
    JOIN unit_section us ON us.id = tb.section_id
    JOIN learning_unit lu ON lu.id = us.unit_id  -- FIXED: was us.learning_unit_id
    JOIN course_learning_unit_assignment cua ON cua.learning_unit_id = lu.id
    WHERE cua.course_id = p_course_id
    ORDER BY us.order_in_unit, tb.title;
END;
$$;

-- Fix feedback submission - add page_identifier column to feedback table
ALTER TABLE feedback 
ADD COLUMN IF NOT EXISTS page_identifier TEXT;

-- Update the feedback table policies to be more permissive if needed
-- (The submit_feedback function will now work with the new column)

-- Fix get_submission_status_matrix - add student_id to the returned columns
CREATE OR REPLACE FUNCTION public.get_submission_status_matrix(
    p_session_id TEXT,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    student_id UUID,  -- FIXED: Added this column
    student_name TEXT,
    task_id UUID,
    task_title TEXT,
    section_id UUID,
    section_title TEXT,
    order_in_section INT,
    order_in_unit INT,
    has_submission BOOLEAN,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ
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

    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RAISE EXCEPTION 'Unauthorized: Only teachers can view submission matrix';
    END IF;

    -- Check teacher authorization
    IF NOT EXISTS (
        SELECT 1 FROM learning_unit lu
        WHERE lu.id = p_unit_id AND lu.creator_id = v_user_id
    ) THEN
        RAISE EXCEPTION 'Unauthorized: Teacher does not own this learning unit';
    END IF;

    -- Get submission status matrix
    RETURN QUERY
    WITH enrolled_students AS (
        SELECT DISTINCT cs.student_id, p.name as student_name
        FROM course_student cs
        JOIN profiles p ON p.id = cs.student_id
        WHERE cs.course_id = p_course_id
    ),
    unit_tasks AS (
        SELECT 
            t.id as task_id,
            t.title as task_title,
            t.section_id,
            s.title as section_title,
            rt.order_in_section,
            s.order_in_unit
        FROM task_base t
        JOIN unit_section s ON s.id = t.section_id
        JOIN regular_tasks rt ON rt.task_id = t.id
        WHERE s.unit_id = p_unit_id  -- FIXED: was s.learning_unit_id
    ),
    submission_status AS (
        SELECT 
            es.student_id,
            ut.task_id,
            COUNT(sub.id) > 0 as has_submission,
            BOOL_OR(sub.is_correct) as is_correct,
            MAX(sub.submitted_at) as submitted_at
        FROM enrolled_students es
        CROSS JOIN unit_tasks ut
        LEFT JOIN submission sub ON 
            sub.student_id = es.student_id AND 
            sub.task_id = ut.task_id
        GROUP BY es.student_id, ut.task_id
    )
    SELECT 
        es.student_id,  -- FIXED: Now included in output
        es.student_name,
        ut.task_id,
        ut.task_title,
        ut.section_id,
        ut.section_title,
        ut.order_in_section,
        ut.order_in_unit,
        ss.has_submission,
        ss.is_correct,
        ss.submitted_at
    FROM enrolled_students es
    CROSS JOIN unit_tasks ut
    LEFT JOIN submission_status ss ON 
        ss.student_id = es.student_id AND 
        ss.task_id = ut.task_id
    ORDER BY es.student_name, ut.order_in_unit, ut.order_in_section;
END;
$$;