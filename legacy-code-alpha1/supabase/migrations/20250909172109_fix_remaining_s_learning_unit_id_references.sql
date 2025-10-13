-- Fix the 3-parameter get_next_due_mastery_task function that still has s.learning_unit_id issues
-- This function wasn't fixed in the previous migration

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
    concept_explanation TEXT,
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
        -- Get all mastery tasks for the course - FIXED: schema references
        SELECT
            t.id as task_id,
            t.title as task_title,
            t.section_id,
            s.title as section_title,
            s.unit_id,  -- FIXED: was s.learning_unit_id
            lu.title as unit_title,
            t.difficulty_level,
            t.concept_explanation,
            t.prompt
        FROM task_base t  -- FIXED: was all_mastery_tasks
        JOIN mastery_tasks mt ON mt.task_id = t.id  -- FIXED: added proper mastery task join
        JOIN unit_section s ON s.id = t.section_id
        JOIN learning_unit lu ON lu.id = s.unit_id  -- FIXED: was s.learning_unit_id
        JOIN course_learning_unit_assignment cua ON cua.unit_id = lu.id  -- FIXED: was cua.learning_unit_id
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
        tp.concept_explanation,
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