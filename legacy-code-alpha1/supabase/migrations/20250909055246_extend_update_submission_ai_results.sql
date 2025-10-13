-- Extend update_submission_ai_results to support all AI result fields
-- This migration creates an extended version that handles all fields in one RPC call

-- Extended function that supports all AI result fields
CREATE OR REPLACE FUNCTION public.update_submission_ai_results_extended(
    p_session_id TEXT,
    p_submission_id UUID,
    p_is_correct BOOLEAN,
    p_ai_feedback TEXT,
    p_criteria_analysis TEXT DEFAULT NULL,
    p_ai_grade TEXT DEFAULT NULL,
    p_feed_back_text TEXT DEFAULT NULL,
    p_feed_forward_text TEXT DEFAULT NULL
)
RETURNS VOID
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
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- This function should be called by the system after AI processing
    -- For now, we allow both students (for their own) and teachers
    IF v_user_role = 'student' THEN
        -- Verify student owns the submission
        IF NOT EXISTS (
            SELECT 1 FROM submission s
            WHERE s.id = p_submission_id AND s.student_id = v_user_id
        ) THEN
            RAISE EXCEPTION 'Unauthorized: Student does not own submission';
        END IF;
    END IF;

    -- Update submission with all fields
    UPDATE submission
    SET 
        is_correct = p_is_correct,
        ai_feedback = p_ai_feedback,
        ai_feedback_generated_at = NOW(),
        ai_criteria_analysis = COALESCE(p_criteria_analysis, ai_criteria_analysis),
        ai_grade = COALESCE(p_ai_grade, ai_grade),
        grade_generated_at = CASE 
            WHEN p_ai_grade IS NOT NULL THEN NOW() 
            ELSE grade_generated_at 
        END,
        feed_back_text = COALESCE(p_feed_back_text, feed_back_text),
        feed_forward_text = COALESCE(p_feed_forward_text, feed_forward_text)
    WHERE id = p_submission_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.update_submission_ai_results_extended TO anon;

-- Also create a simpler mark_feedback_as_viewed function that uses RPC pattern
-- The existing one might have issues with the direct client update
CREATE OR REPLACE FUNCTION public.mark_feedback_as_viewed(
    p_session_id TEXT,
    p_submission_id UUID
)
RETURNS BOOLEAN
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_updated_count INTEGER;
BEGIN
    -- Session validation
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RAISE EXCEPTION 'Unauthorized: Invalid session';
    END IF;

    -- Mark feedback as viewed
    -- Only update if user is the student who owns the submission
    UPDATE submission
    SET feedback_viewed_at = NOW()
    WHERE id = p_submission_id
    AND student_id = v_user_id
    AND feedback_viewed_at IS NULL;
    
    -- Get the number of affected rows
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    -- Return true if a row was updated
    RETURN v_updated_count > 0;
END;
$$;

GRANT EXECUTE ON FUNCTION public.mark_feedback_as_viewed TO anon;

-- Add helpful comments
COMMENT ON FUNCTION public.update_submission_ai_results_extended IS 'Extended version of update_submission_ai_results that supports all AI result fields including criteria analysis, grades, and feedback texts';
COMMENT ON FUNCTION public.mark_feedback_as_viewed IS 'Improved version of mark_feedback_as_viewed_safe that returns success status';