-- Fix get_remaining_attempts to return both remaining and max attempts
-- This migration updates the function to match the expected Python return format

-- Drop the existing function first
DROP FUNCTION IF EXISTS public.get_remaining_attempts(TEXT, UUID, UUID);

-- Recreate with proper return type
CREATE OR REPLACE FUNCTION public.get_remaining_attempts(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    remaining_attempts INT,
    max_attempts INT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_max_attempts INT;
    v_attempt_count INT;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        -- Return NULL values for invalid session
        RETURN QUERY SELECT NULL::INT, NULL::INT;
        RETURN;
    END IF;

    -- Check permissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        -- Return NULL values for unauthorized access
        RETURN QUERY SELECT NULL::INT, NULL::INT;
        RETURN;
    END IF;

    -- Get max attempts for regular task
    SELECT t.max_attempts
    INTO v_max_attempts
    FROM all_regular_tasks t
    WHERE t.id = p_task_id;

    IF NOT FOUND THEN
        -- Check if it's a mastery task (unlimited attempts)
        IF EXISTS (SELECT 1 FROM all_mastery_tasks WHERE id = p_task_id) THEN
            -- Mastery tasks have unlimited attempts - return special values
            RETURN QUERY SELECT NULL::INT as remaining_attempts, NULL::INT as max_attempts;
        ELSE
            -- Task not found - return zeros
            RETURN QUERY SELECT 0::INT as remaining_attempts, 0::INT as max_attempts;
        END IF;
        RETURN;
    END IF;

    -- Count existing attempts
    SELECT COUNT(*)::INT
    INTO v_attempt_count
    FROM submission s
    WHERE s.student_id = p_student_id AND s.task_id = p_task_id;

    -- Return both remaining attempts and max attempts
    RETURN QUERY SELECT 
        GREATEST(0, v_max_attempts - v_attempt_count)::INT as remaining_attempts,
        v_max_attempts as max_attempts;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_remaining_attempts TO anon;

-- Add comment for documentation
COMMENT ON FUNCTION public.get_remaining_attempts IS 'Returns remaining attempts and max attempts for a student on a specific task. Returns NULL values for mastery tasks (unlimited attempts).';