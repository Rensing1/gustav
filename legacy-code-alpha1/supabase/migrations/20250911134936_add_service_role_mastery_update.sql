-- Add service role function for updating mastery progress
-- This is needed for the background worker that processes AI feedback

CREATE OR REPLACE FUNCTION update_mastery_progress_service(
    p_student_id UUID,
    p_task_id UUID,
    p_q_vec JSONB
)
RETURNS JSONB
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_progress RECORD;
    v_rating FLOAT;
    v_new_stability FLOAT;
    v_new_difficulty FLOAT;
    v_next_due DATE;
BEGIN
    -- This function is called by service role, no session validation needed
    
    -- Get current progress if exists
    SELECT * INTO v_current_progress
    FROM student_mastery_progress
    WHERE student_id = p_student_id
    AND task_id = p_task_id;
    
    -- Calculate rating from q_vec (using korrektheit as primary metric)
    v_rating := COALESCE((p_q_vec->>'korrektheit')::FLOAT, 0.5);
    
    -- Simple but effective spaced repetition calculation (same as in submit_mastery_answer_complete)
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
    
    RETURN jsonb_build_object(
        'success', true,
        'new_stability', v_new_stability,
        'next_due_date', v_next_due,
        'message', 'Mastery progress updated successfully'
    );
    
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'success', false,
        'error', SQLERRM
    );
END;
$$;

-- Grant execute to service_role (not to authenticated/anon for security)
GRANT EXECUTE ON FUNCTION update_mastery_progress_service TO service_role;

-- Add comment
COMMENT ON FUNCTION update_mastery_progress_service IS 'Service-role only function for updating mastery progress from background workers';