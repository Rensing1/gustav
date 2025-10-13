-- Fix all references from course_students (plural) to course_student (singular)

-- Fix submit_mastery_answer_complete
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
    
    -- Check authorization for task - FIX: use course_student not course_students
    IF NOT EXISTS (
        SELECT 1 FROM student_mastery_progress smp
        JOIN mastery_tasks mt ON mt.task_id = p_task_id
        JOIN task_base t ON t.id = mt.task_id
        JOIN unit_section us ON us.id = t.section_id
        JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
        JOIN course_student cs ON cs.course_id = clua.course_id  -- FIXED\!
        WHERE cs.student_id = v_user_id
        AND mt.task_id = p_task_id
    ) THEN
        -- Task might not have progress yet, check if student is enrolled
        IF NOT EXISTS (
            SELECT 1 FROM mastery_tasks mt
            JOIN task_base t ON t.id = mt.task_id
            JOIN unit_section us ON us.id = t.section_id
            JOIN course_learning_unit_assignment clua ON clua.unit_id = us.unit_id
            JOIN course_student cs ON cs.course_id = clua.course_id  -- FIXED\!
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
            submitted_at,
            feedback_status  -- Set to completed since we have the feedback
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
            NOW(),
            'completed'
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
GRANT EXECUTE ON FUNCTION submit_mastery_answer_complete TO authenticated;

-- Update comment
COMMENT ON FUNCTION submit_mastery_answer_complete IS 'Submits mastery answer and updates spaced repetition progress atomically';
