-- Migration: Fix mastery functions for Phase 2
-- Purpose: Fix session ID type mismatch and create missing RPC functions

-- 1. Drop the existing function that expects UUID for session_id
DROP FUNCTION IF EXISTS submit_mastery_answer_complete(UUID, UUID, TEXT, JSONB, JSONB);

-- 2. Recreate with TEXT session_id to match other functions
CREATE OR REPLACE FUNCTION submit_mastery_answer_complete(
    p_session_id TEXT,  -- Changed from UUID to TEXT
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
    v_submission_id UUID;
    v_attempt_number INT;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session using TEXT session_id
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization for task
    IF NOT EXISTS (
        SELECT 1 FROM student_mastery_progress smp
        JOIN mastery_tasks mt ON mt.id = p_task_id
        JOIN unit_section us ON us.id = mt.section_id
        JOIN course_units cu ON cu.unit_id = us.unit_id
        JOIN course_students cs ON cs.course_id = cu.course_id
        WHERE cs.student_id = v_user_id
        AND mt.id = p_task_id
    ) THEN
        -- Task might not have progress yet, check if student is enrolled
        IF NOT EXISTS (
            SELECT 1 FROM mastery_tasks mt
            JOIN unit_section us ON us.id = mt.section_id
            JOIN course_units cu ON cu.unit_id = us.unit_id
            JOIN course_students cs ON cs.course_id = cu.course_id
            WHERE cs.student_id = v_user_id
            AND mt.id = p_task_id
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
        
        -- Insert submission
        INSERT INTO submission (
            student_id,
            task_id,
            submission_data,
            ai_criteria_analysis,
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
            (p_ai_assessment->>'q_vec')::JSONB,
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
        -- Value is between 0.0 and 1.0, so scale to 1-5
        v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
        
        -- Simple but effective spaced repetition calculation
        IF v_current_progress.stability IS NULL THEN
            -- First review
            IF v_rating >= 0.6 THEN  -- 60% or better
                v_new_stability := 2.5;  -- Review in 2-3 days
            ELSE
                v_new_stability := 1.0;  -- Review tomorrow
            END IF;
            v_new_difficulty := 5.0; -- Default difficulty
        ELSE
            -- Subsequent reviews
            -- Adjust stability based on performance
            IF v_rating >= 0.8 THEN  -- 80% or better - great retention
                v_new_stability := v_current_progress.stability * 2.5;
            ELSIF v_rating >= 0.6 THEN  -- 60-79% - good retention
                v_new_stability := v_current_progress.stability * 1.5;
            ELSIF v_rating >= 0.4 THEN  -- 40-59% - ok retention
                v_new_stability := v_current_progress.stability * 1.1;
            ELSE  -- Below 40% - poor retention, reduce interval
                v_new_stability := v_current_progress.stability * 0.5;
            END IF;
            
            -- Cap maximum stability at 90 days
            v_new_stability := LEAST(v_new_stability, 90.0);
            
            -- Minimum stability is 1 day
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

-- 3. Create missing get_mastery_stats_for_student function
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
BEGIN
    -- Get user from session
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization (student viewing own stats or teacher)
    IF v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = v_user_id
            AND role IN ('admin', 'teacher')
        ) THEN
            RAISE EXCEPTION 'Not authorized to view other users stats';
        END IF;
        
        -- Teacher must be teaching the course
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
            mt.id as task_id,
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
        JOIN unit_section us ON us.id = mt.section_id
        JOIN course_units cu ON cu.unit_id = us.unit_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.id 
            AND smp.student_id = p_student_id
        WHERE cu.course_id = p_course_id
    ),
    recent_submissions AS (
        SELECT DISTINCT
            s.task_id,
            (s.ai_criteria_analysis->>'korrektheit')::FLOAT as rating
        FROM submission s
        JOIN mastery_tasks mt ON mt.id = s.task_id
        JOIN unit_section us ON us.id = mt.section_id
        JOIN course_units cu ON cu.unit_id = us.unit_id
        WHERE s.student_id = p_student_id
        AND cu.course_id = p_course_id
        AND s.submitted_at >= CURRENT_DATE - INTERVAL '30 days'
        AND s.ai_criteria_analysis IS NOT NULL
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
        0 as streak_days  -- Will be calculated by separate function
    FROM task_stats ts
    LEFT JOIN recent_submissions rs ON rs.task_id = ts.task_id;
END;
$$;

-- 4. Add session validation to get_mastery_summary
DROP FUNCTION IF EXISTS get_mastery_summary(UUID, UUID);

CREATE OR REPLACE FUNCTION get_mastery_summary(
    p_session_id TEXT,  -- Added session parameter
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
BEGIN
    -- Get user from session
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = v_user_id
            AND role IN ('admin', 'teacher')
        ) THEN
            RAISE EXCEPTION 'Not authorized to view other users data';
        END IF;
    END IF;
    
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.id,
            CASE
                WHEN smp.stability > 21 THEN 'mastered'
                WHEN smp.stability IS NOT NULL THEN 'learning'
                ELSE 'not_started'
            END as status,
            smp.stability,
            smp.next_due_date
        FROM mastery_tasks mt
        JOIN unit_section us ON us.id = mt.section_id
        JOIN course_units cu ON cu.unit_id = us.unit_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.id 
            AND smp.student_id = p_student_id
        WHERE cu.course_id = p_course_id
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

-- 5. Add session validation to get_due_tomorrow_count
DROP FUNCTION IF EXISTS get_due_tomorrow_count(UUID, UUID);

CREATE OR REPLACE FUNCTION get_due_tomorrow_count(
    p_session_id TEXT,  -- Added session parameter
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
    v_count INT;
BEGIN
    -- Get user from session
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check authorization
    IF v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = v_user_id
            AND role IN ('admin', 'teacher')
        ) THEN
            RAISE EXCEPTION 'Not authorized to view other users data';
        END IF;
    END IF;
    
    SELECT COUNT(*)::INT INTO v_count
    FROM student_mastery_progress smp
    JOIN mastery_tasks mt ON mt.id = smp.task_id
    JOIN unit_section us ON us.id = mt.section_id
    JOIN course_units cu ON cu.unit_id = us.unit_id
    WHERE smp.student_id = p_student_id
    AND cu.course_id = p_course_id
    AND smp.next_due_date = CURRENT_DATE + INTERVAL '1 day';
    
    RETURN v_count;
END;
$$;

-- 6. Update existing update_mastery_progress to accept TEXT session_id
DROP FUNCTION IF EXISTS update_mastery_progress(UUID, UUID, UUID, JSONB);

CREATE OR REPLACE FUNCTION update_mastery_progress(
    p_session_id TEXT,  -- Changed from UUID to TEXT
    p_student_id UUID,
    p_task_id UUID,
    p_q_vec JSONB
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Check if teacher updating for student
    IF v_user_id != p_student_id THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = v_user_id
            AND role IN ('admin', 'teacher')
        ) THEN
            RAISE EXCEPTION 'Not authorized to update progress for other users';
        END IF;
    END IF;
    
    -- Get current progress
    SELECT * INTO v_current_progress
    FROM student_mastery_progress
    WHERE student_id = p_student_id
    AND task_id = p_task_id;
    
    -- Calculate rating from q_vec
    v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
    
    -- Calculate new values (same algorithm as in submit_mastery_answer_complete)
    IF v_current_progress.stability IS NULL THEN
        IF v_rating >= 0.6 THEN
            v_new_stability := 2.5;
        ELSE
            v_new_stability := 1.0;
        END IF;
        v_new_difficulty := 5.0;
    ELSE
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
    
    v_next_due := CURRENT_DATE + INTERVAL '1 day' * ROUND(v_new_stability);
    
    -- Update progress
    INSERT INTO student_mastery_progress (
        student_id,
        task_id,
        difficulty,
        stability,
        last_reviewed_at,
        next_due_date
    )
    VALUES (
        p_student_id,
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
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION submit_mastery_answer_complete TO authenticated;
GRANT EXECUTE ON FUNCTION get_mastery_stats_for_student TO authenticated;
GRANT EXECUTE ON FUNCTION get_mastery_summary TO authenticated;
GRANT EXECUTE ON FUNCTION get_due_tomorrow_count TO authenticated;
GRANT EXECUTE ON FUNCTION update_mastery_progress TO authenticated;

-- Comment the functions
COMMENT ON FUNCTION submit_mastery_answer_complete IS 'Atomically saves submission and updates mastery progress with improved spaced repetition algorithm';
COMMENT ON FUNCTION get_mastery_stats_for_student IS 'Gets comprehensive mastery statistics for a student in a course';
COMMENT ON FUNCTION get_mastery_summary IS 'Gets compact mastery summary with session validation';
COMMENT ON FUNCTION get_due_tomorrow_count IS 'Gets count of tasks due tomorrow with session validation';
COMMENT ON FUNCTION update_mastery_progress IS 'Updates mastery progress with session validation';