-- Migration: Fix references to auth.session_user_id
-- Purpose: Update all functions that incorrectly reference auth.session_user_id to use public.session_user_id

-- 1. Update submit_mastery_answer_complete
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
    v_submission_id UUID;
    v_attempt_number INT;
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session using public.session_user_id
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

-- 2. Update get_mastery_stats_for_student
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
        0 as streak_days
    FROM task_stats ts
    LEFT JOIN recent_submissions rs ON rs.task_id = ts.task_id;
END;
$$;

-- 3. Update get_mastery_summary  
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

-- 4. Update get_due_tomorrow_count
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

-- 5. Update update_mastery_progress
CREATE OR REPLACE FUNCTION update_mastery_progress(
    p_session_id TEXT,
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

-- 6. Update get_submission_by_id
CREATE OR REPLACE FUNCTION get_submission_by_id(
    p_session_id TEXT,
    p_submission_id UUID
)
RETURNS TABLE (
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_text TEXT,
    submission_data JSONB,
    is_correct BOOLEAN,
    submitted_at TIMESTAMP WITH TIME ZONE,
    attempt_number INT,
    -- Feedback queue fields
    feedback_status TEXT,
    retry_count INT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    -- AI feedback fields
    ai_feedback TEXT,
    ai_feedback_generated_at TIMESTAMP WITH TIME ZONE,
    ai_insights JSONB,
    ai_criteria_analysis JSONB,
    feed_back_text TEXT,
    feed_forward_text TEXT,
    -- Teacher feedback fields
    teacher_feedback TEXT,
    teacher_feedback_generated_at TIMESTAMP WITH TIME ZONE,
    teacher_override_feedback TEXT,
    teacher_override_grade TEXT,
    override_grade BOOLEAN,
    feedback_viewed_at TIMESTAMP WITH TIME ZONE
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_student_id UUID;
    v_is_teacher BOOLEAN;
BEGIN
    -- Get user from session
    SELECT public.session_user_id(p_session_id) INTO v_user_id;
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Get student_id from submission
    SELECT s.student_id INTO v_student_id
    FROM submission s
    WHERE s.id = p_submission_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;
    
    -- Check if user is a teacher
    SELECT EXISTS(
        SELECT 1 FROM user_roles 
        WHERE user_id = v_user_id 
        AND role IN ('teacher', 'admin')
    ) INTO v_is_teacher;
    
    -- Authorization: student can view own submissions, teachers can view all
    IF v_user_id != v_student_id AND NOT v_is_teacher THEN
        RAISE EXCEPTION 'Not authorized to view this submission';
    END IF;
    
    -- Return submission details
    RETURN QUERY
    SELECT 
        s.id,
        s.student_id,
        s.task_id,
        CASE 
            WHEN s.submission_data IS NOT NULL THEN s.submission_data::text
            ELSE s.submission_text 
        END as submission_text,
        s.submission_data,
        s.is_correct,
        s.submitted_at,
        s.attempt_number,
        -- Feedback queue fields
        s.feedback_status,
        s.retry_count,
        s.processing_started_at,
        -- AI feedback fields
        s.ai_feedback,
        s.ai_feedback_generated_at,
        s.ai_insights,
        s.ai_criteria_analysis,
        s.feed_back_text,
        s.feed_forward_text,
        -- Teacher feedback fields
        s.teacher_feedback,
        s.teacher_feedback_generated_at,
        s.teacher_override_feedback,
        s.teacher_override_grade,
        s.override_grade,
        s.feedback_viewed_at
    FROM submission s
    WHERE s.id = p_submission_id;
END;
$$;