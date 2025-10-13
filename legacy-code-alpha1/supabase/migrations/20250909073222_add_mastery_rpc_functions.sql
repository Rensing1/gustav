-- Migration: Add missing RPC functions for mastery learning
-- Purpose: Support HttpOnly cookie authentication for mastery features

-- Function: submit_mastery_answer_complete
-- Atomically saves submission and updates mastery progress
CREATE OR REPLACE FUNCTION submit_mastery_answer_complete(
    p_session_id UUID,
    p_task_id UUID,
    p_submission_text TEXT,
    p_ai_assessment JSONB,
    p_q_vec JSONB
)
RETURNS JSONB
SECURITY DEFINER
SET search_path = public, auth
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_submission_id UUID;
    v_attempt_number INT;
    v_current_progress RECORD;
    v_rating INT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT user_id INTO v_user_id
    FROM user_sessions
    WHERE session_id = p_session_id
    AND expires_at > NOW();
    
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
        RAISE EXCEPTION 'Not authorized for this task';
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
        
        -- Calculate rating from q_vec (simple version)
        v_rating := GREATEST(1, LEAST(5, 
            ROUND((p_q_vec->>'korrektheit')::FLOAT * 4) + 1
        ));
        
        -- Simple spaced repetition calculation
        IF v_current_progress.stability IS NULL THEN
            -- First review
            v_new_stability := CASE 
                WHEN v_rating >= 3 THEN 2.5
                ELSE 1.3
            END;
            v_new_difficulty := 5.0; -- Default difficulty
        ELSE
            -- Subsequent reviews
            v_new_stability := v_current_progress.stability * 
                CASE 
                    WHEN v_rating >= 3 THEN 1.3
                    ELSE 0.6
                END;
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
            'success', true
        );
        
    EXCEPTION WHEN OTHERS THEN
        -- Rollback will happen automatically
        RAISE;
    END;
END;
$$;

-- Function: update_mastery_progress (standalone)
CREATE OR REPLACE FUNCTION update_mastery_progress(
    p_session_id UUID,
    p_student_id UUID,
    p_task_id UUID,
    p_q_vec JSONB
)
RETURNS VOID
SECURITY DEFINER
SET search_path = public, auth
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
    v_current_progress RECORD;
    v_rating INT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- Get user from session
    SELECT user_id INTO v_user_id
    FROM user_sessions
    WHERE session_id = p_session_id
    AND expires_at > NOW();
    
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
    v_rating := GREATEST(1, LEAST(5, 
        ROUND((p_q_vec->>'korrektheit')::FLOAT * 4) + 1
    ));
    
    -- Calculate new values
    IF v_current_progress.stability IS NULL THEN
        v_new_stability := CASE 
            WHEN v_rating >= 3 THEN 2.5
            ELSE 1.3
        END;
        v_new_difficulty := 5.0;
    ELSE
        v_new_stability := v_current_progress.stability * 
            CASE 
                WHEN v_rating >= 3 THEN 1.3
                ELSE 0.6
            END;
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
GRANT EXECUTE ON FUNCTION update_mastery_progress TO authenticated;