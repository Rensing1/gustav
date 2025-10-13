-- Migration: Fix course_units table references
-- Purpose: Replace all references to non-existent course_units with course_learning_unit_assignment

-- Drop and recreate all functions that use wrong table name

-- 1. Fix get_mastery_stats_for_student
DROP FUNCTION IF EXISTS get_mastery_stats_for_student(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION get_mastery_stats_for_student(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    total_tasks INT,
    completed_tasks INT,
    due_today INT,
    overdue INT,
    upcoming INT,
    completion_rate FLOAT,
    average_rating FLOAT,
    streak_days INT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization (student viewing own stats or teacher)
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users stats';
    END IF;
    
    -- Teacher must be teaching the course
    IF v_user_id != p_student_id AND v_user_role = 'teacher' THEN
        IF NOT EXISTS (
            SELECT 1 FROM course_teachers
            WHERE teacher_id = v_user_id
            AND course_id = p_course_id
        ) THEN
            RAISE EXCEPTION 'Not authorized for this course';
        END IF;
    END IF;
    
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.task_id,
            smp.next_due_date,
            smp.last_reviewed_at,
            CASE
                WHEN smp.last_reviewed_at IS NOT NULL THEN 1
                ELSE 0
            END as is_completed,
            CASE
                WHEN smp.next_due_date = CURRENT_DATE THEN 1
                ELSE 0
            END as is_due_today,
            CASE
                WHEN smp.next_due_date < CURRENT_DATE THEN 1
                ELSE 0
            END as is_overdue,
            CASE
                WHEN smp.next_due_date > CURRENT_DATE THEN 1
                ELSE 0
            END as is_upcoming
        FROM mastery_tasks mt
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.task_id 
            AND smp.student_id = p_student_id
        WHERE clua.course_id = p_course_id
    ),
    recent_submissions AS (
        SELECT DISTINCT
            s.task_id,
            (s.ai_insights->>'korrektheit')::FLOAT as rating
        FROM submission s
        JOIN mastery_tasks mt ON mt.task_id = s.task_id
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        WHERE s.student_id = p_student_id
        AND clua.course_id = p_course_id
        AND s.submitted_at >= CURRENT_DATE - INTERVAL '30 days'
        AND s.ai_insights IS NOT NULL
    )
    SELECT
        COUNT(DISTINCT ts.task_id)::INT as total_tasks,
        SUM(ts.is_completed)::INT as completed_tasks,
        SUM(ts.is_due_today)::INT as due_today,
        SUM(ts.is_overdue)::INT as overdue,
        SUM(ts.is_upcoming)::INT as upcoming,
        CASE
            WHEN COUNT(DISTINCT ts.task_id) > 0 
            THEN (SUM(ts.is_completed)::FLOAT / COUNT(DISTINCT ts.task_id)::FLOAT)
            ELSE 0.0
        END as completion_rate,
        COALESCE(AVG(rs.rating), 0.0) as average_rating,
        0 as streak_days
    FROM task_stats ts
    LEFT JOIN recent_submissions rs ON rs.task_id = ts.task_id;
END;
$$;

-- 2. Fix get_mastery_summary
DROP FUNCTION IF EXISTS get_mastery_summary(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION get_mastery_summary(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    total INT,
    mastered INT,
    learning INT,
    not_started INT,
    due_today INT,
    avg_stability FLOAT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users data';
    END IF;
    
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.task_id,
            CASE
                WHEN smp.stability > 21 THEN 'mastered'
                WHEN smp.stability IS NOT NULL THEN 'learning'
                ELSE 'not_started'
            END as status,
            smp.stability,
            smp.next_due_date
        FROM mastery_tasks mt
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.task_id 
            AND smp.student_id = p_student_id
        WHERE clua.course_id = p_course_id
    )
    SELECT
        COUNT(*)::INT as total,
        COUNT(CASE WHEN status = 'mastered' THEN 1 END)::INT as mastered,
        COUNT(CASE WHEN status = 'learning' THEN 1 END)::INT as learning,
        COUNT(CASE WHEN status = 'not_started' THEN 1 END)::INT as not_started,
        COUNT(CASE WHEN next_due_date <= CURRENT_DATE THEN 1 END)::INT as due_today,
        COALESCE(AVG(stability), 1.0)::FLOAT as avg_stability
    FROM task_stats;
END;
$$;

-- 3. Fix get_due_tomorrow_count
DROP FUNCTION IF EXISTS get_due_tomorrow_count(TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION get_due_tomorrow_count(
    p_session_id TEXT,
    p_student_id UUID,
    p_course_id UUID
)
RETURNS INT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_count INT;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id AND v_user_role NOT IN ('admin', 'teacher') THEN
        RAISE EXCEPTION 'Not authorized to view other users data';
    END IF;
    
    SELECT COUNT(*)::INT INTO v_count
    FROM student_mastery_progress smp
    JOIN mastery_tasks mt ON mt.task_id = smp.task_id
    JOIN task_base t ON t.id = mt.task_id
    JOIN unit_section us ON us.id = t.section_id
    JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id  -- Correct table!
    WHERE smp.student_id = p_student_id
    AND clua.course_id = p_course_id
    AND smp.next_due_date = CURRENT_DATE + INTERVAL '1 day';
    
    RETURN v_count;
END;
$$;

-- 4. Fix submit_mastery_answer_complete
DROP FUNCTION IF EXISTS submit_mastery_answer_complete(TEXT, UUID, TEXT, JSONB, JSONB);

CREATE OR REPLACE FUNCTION submit_mastery_answer_complete(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_text TEXT,
    p_ai_assessment JSONB,
    p_q_vec JSONB
)
RETURNS JSONB
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_submission_id UUID;
    v_attempt_number INT;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization for task - correct joins!
    IF NOT EXISTS (
        SELECT 1 FROM student_mastery_progress smp
        JOIN mastery_tasks mt ON mt.task_id = p_task_id
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
        JOIN course_students cs ON cs.course_id = clua.course_id
        WHERE cs.student_id = v_user_id
        AND mt.task_id = p_task_id
    ) THEN
        -- Task might not have progress yet, check if student is enrolled
        IF NOT EXISTS (
            SELECT 1 FROM mastery_tasks mt
            JOIN task_base t ON t.id = mt.task_id
            JOIN unit_section us ON us.id = t.section_id
            JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
            JOIN course_students cs ON cs.course_id = clua.course_id
            WHERE cs.student_id = v_user_id
            AND mt.task_id = p_task_id
        ) THEN
            RAISE EXCEPTION 'Not authorized for this task';
        END IF;
    END IF;
    
    -- Start transaction
    BEGIN
        -- Count existing attempts
        SELECT COUNT(*) + 1 INTO v_attempt_number
        FROM submission
        WHERE student_id = v_user_id
        AND task_id = p_task_id;
        
        -- Insert submission with correct column names
        INSERT INTO submission (
            student_id,
            task_id,
            submission_data,
            ai_insights,
            feed_back_text,
            feed_forward_text,
            ai_feedback,
            attempt_number,
            submitted_at
        )
        VALUES (
            v_user_id,
            p_task_id,
            p_submission_text::JSONB,
            p_q_vec,
            p_ai_assessment->>'feed_back_text',
            p_ai_assessment->>'feed_forward_text',
            p_ai_assessment->>'ai_feedback',
            v_attempt_number,
            NOW()
        )
        RETURNING id INTO v_submission_id;
        
        -- Get current progress if exists
        SELECT * INTO v_current_progress
        FROM student_mastery_progress
        WHERE student_id = v_user_id
        AND task_id = p_task_id;
        
        -- Calculate rating from q_vec (using korrektheit as primary metric)
        v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
        
        -- Simple but effective spaced repetition calculation
        IF v_current_progress.stability IS NULL THEN
            -- First review
            IF v_rating >= 0.6 THEN
                v_new_stability := 2.5;
            ELSE
                v_new_stability := 1.0;
            END IF;
            v_new_difficulty := 5.0;
        ELSE
            -- Subsequent reviews
            IF v_rating >= 0.8 THEN
                v_new_stability := v_current_progress.stability * 2.5;
            ELSIF v_rating >= 0.6 THEN
                v_new_stability := v_current_progress.stability * 1.5;
            ELSIF v_rating >= 0.4 THEN
                v_new_stability := v_current_progress.stability * 1.1;
            ELSE
                v_new_stability := v_current_progress.stability * 0.5;
            END IF;
            
            v_new_stability := LEAST(v_new_stability, 90.0);
            v_new_stability := GREATEST(v_new_stability, 1.0);
            
            v_new_difficulty := v_current_progress.difficulty;
        END IF;
        
        -- Calculate next due date
        v_next_due := CURRENT_DATE + INTERVAL '1 day' * ROUND(v_new_stability);
        
        -- Upsert progress
        INSERT INTO student_mastery_progress (
            student_id,
            task_id,
            difficulty,
            stability,
            last_reviewed_at,
            next_due_date
        )
        VALUES (
            v_user_id,
            p_task_id,
            v_new_difficulty,
            v_new_stability,
            NOW(),
            v_next_due
        )
        ON CONFLICT (student_id, task_id)
        DO UPDATE SET
            difficulty = EXCLUDED.difficulty,
            stability = EXCLUDED.stability,
            last_reviewed_at = EXCLUDED.last_reviewed_at,
            next_due_date = EXCLUDED.next_due_date;
        
        RETURN jsonb_build_object(
            'submission_id', v_submission_id,
            'success', true,
            'next_review_date', v_next_due,
            'stability', v_new_stability
        );
        
    EXCEPTION WHEN OTHERS THEN
        -- Rollback will happen automatically
        RAISE;
    END;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_mastery_stats_for_student TO authenticated;
GRANT EXECUTE ON FUNCTION get_mastery_summary TO authenticated;
GRANT EXECUTE ON FUNCTION get_due_tomorrow_count TO authenticated;
GRANT EXECUTE ON FUNCTION submit_mastery_answer_complete TO authenticated;

-- Add comments
COMMENT ON FUNCTION get_mastery_stats_for_student IS 'Gets mastery statistics with correct course_learning_unit_assignment table';
COMMENT ON FUNCTION get_mastery_summary IS 'Gets mastery summary with correct course_learning_unit_assignment table';
COMMENT ON FUNCTION get_due_tomorrow_count IS 'Gets due tomorrow count with correct course_learning_unit_assignment table';
COMMENT ON FUNCTION submit_mastery_answer_complete IS 'Submits mastery answer with correct course_learning_unit_assignment table';