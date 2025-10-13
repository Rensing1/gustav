-- Fix get_submission_for_task to return all feedback fields
-- This migration adds missing feedback fields to the function return

-- Drop the old function
DROP FUNCTION IF EXISTS public.get_submission_for_task(TEXT, UUID, UUID);

-- Recreate with all feedback fields
CREATE OR REPLACE FUNCTION public.get_submission_for_task(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    submission_data JSONB,
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    grade TEXT,
    -- New fields for complete feedback support:
    ai_insights JSONB,
    feed_back_text TEXT,
    feed_forward_text TEXT,
    teacher_override_feedback TEXT,
    teacher_override_grade TEXT,
    feedback_status TEXT,
    attempt_number INTEGER
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
        RAISE EXCEPTION 'Invalid session';
    END IF;

    -- Permission check: students can only see their own submissions
    IF v_user_role = 'student' AND v_user_id != p_student_id THEN
        RAISE EXCEPTION 'Unauthorized: Students can only view their own submissions';
    END IF;

    -- Return the latest submission with all feedback fields
    RETURN QUERY
    SELECT 
        s.id,
        s.submission_data,
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        COALESCE(s.teacher_override_grade, s.ai_grade) as grade,
        -- Additional feedback fields:
        s.ai_insights,
        s.feed_back_text,
        s.feed_forward_text,
        s.teacher_override_feedback,
        s.teacher_override_grade,
        s.feedback_status,
        s.attempt_number
    FROM submission s
    WHERE s.student_id = p_student_id 
    AND s.task_id = p_task_id
    ORDER BY s.submitted_at DESC
    LIMIT 1;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.get_submission_for_task(TEXT, UUID, UUID) TO anon;

-- Add comment for documentation
COMMENT ON FUNCTION public.get_submission_for_task(TEXT, UUID, UUID) IS 
'Gets the latest submission for a student-task pair with all feedback fields including ai_insights, structured feedback, and teacher overrides';