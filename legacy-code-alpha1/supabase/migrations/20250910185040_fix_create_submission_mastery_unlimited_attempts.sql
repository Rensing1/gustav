-- Fix create_submission function to properly handle unlimited attempts for mastery tasks
-- The previous migration broke mastery task logic by applying max_attempts to all tasks
-- This restores the correct behavior: unlimited attempts for mastery, limited for regular tasks

-- Drop all existing function overloads first to allow return type change
DROP FUNCTION IF EXISTS create_submission(TEXT, UUID, TEXT);
DROP FUNCTION IF EXISTS create_submission(UUID, UUID, TEXT);
DROP FUNCTION IF EXISTS create_submission CASCADE;

CREATE OR REPLACE FUNCTION create_submission(
    p_session_id TEXT,
    p_task_id UUID,
    p_submission_text TEXT
) RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_section_id UUID;
    v_max_attempts INT;
    v_is_mastery BOOLEAN := FALSE;
    v_attempt_count INT;
    v_submission_id UUID;
    v_submission_data JSONB;
BEGIN
    -- Get user from session
    SELECT user_id INTO v_user_id
    FROM user_sessions 
    WHERE session_id = p_session_id 
    AND expires_at > NOW();
    
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;

    -- Check if task exists in regular tasks first
    SELECT 
        t.section_id,
        t.max_attempts,
        FALSE
    INTO v_section_id, v_max_attempts, v_is_mastery
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    -- If not found in regular tasks, check mastery tasks
    IF NOT FOUND THEN
        SELECT 
            t.section_id,
            NULL::INT, -- Mastery tasks have unlimited attempts
            TRUE
        INTO v_section_id, v_max_attempts, v_is_mastery
        FROM all_mastery_tasks t
        WHERE t.id = p_task_id;
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Task not found';
        END IF;
    END IF;

    -- Check attempt limit ONLY for regular tasks (not mastery tasks)
    IF NOT v_is_mastery AND v_max_attempts IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_attempt_count
        FROM submission s
        WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

        IF v_attempt_count >= v_max_attempts THEN
            RAISE EXCEPTION 'Maximum attempts exceeded for this task';
        END IF;
    END IF;

    -- Calculate attempt number (for both regular and mastery tasks)
    SELECT COALESCE(MAX(attempt_number), 0) + 1
    INTO v_attempt_count
    FROM submission s
    WHERE s.student_id = v_user_id AND s.task_id = p_task_id;

    -- Generate new submission ID
    v_submission_id := gen_random_uuid();

    -- Insert submission with proper defaults for queue processing
    INSERT INTO submission (
        id,
        student_id,
        task_id,
        submission_data,
        attempt_number,
        submitted_at,
        feedback_status,
        retry_count,
        last_retry_at,
        processing_started_at
    ) VALUES (
        v_submission_id,
        v_user_id,
        p_task_id,
        p_submission_text::JSONB,
        v_attempt_count,
        NOW(),
        'pending',    -- Default status for queue processing
        0,            -- Start with 0 retries
        NULL,         -- No retries yet
        NULL          -- Not processing yet
    );

    -- Return the created submission
    SELECT jsonb_build_object(
        'id', s.id,
        'student_id', s.student_id,
        'task_id', s.task_id,
        'submission_data', s.submission_data,
        'attempt_number', s.attempt_number,
        'submitted_at', s.submitted_at,
        'feedback_status', s.feedback_status,
        'is_mastery_task', v_is_mastery
    ) INTO v_submission_data
    FROM submission s
    WHERE s.id = v_submission_id;

    RETURN v_submission_data;
END;
$$;

-- Grant execute permission to anon role for session-based access
GRANT EXECUTE ON FUNCTION create_submission(TEXT, UUID, TEXT) TO anon;

-- Add comment explaining the fix
COMMENT ON FUNCTION create_submission IS 'Creates a new submission with proper mastery task handling. Regular tasks respect max_attempts limits, mastery tasks have unlimited attempts for spaced repetition learning.';