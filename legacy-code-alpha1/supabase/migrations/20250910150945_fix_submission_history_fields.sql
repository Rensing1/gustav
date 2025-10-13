-- Fix submission history to include attempt_number and proper field names

DROP FUNCTION IF EXISTS public.get_submission_history(TEXT, UUID, UUID);

CREATE FUNCTION public.get_submission_history(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE (
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_data JSONB,  -- Return as JSONB, not TEXT
    submission_text TEXT,   -- For backwards compatibility
    is_correct BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE,  -- UI expects created_at
    submitted_at TIMESTAMP WITH TIME ZONE,  -- Also include submitted_at
    ai_feedback TEXT,
    ai_feedback_generated_at TIMESTAMP WITH TIME ZONE,
    teacher_feedback TEXT,
    teacher_feedback_generated_at TIMESTAMP WITH TIME ZONE,
    override_grade BOOLEAN,
    feedback_viewed_at TIMESTAMP WITH TIME ZONE,
    attempt_number INTEGER,  -- UI expects this!
    feedback_status TEXT,
    ai_grade TEXT,
    teacher_override_feedback TEXT,
    teacher_override_grade TEXT,
    feed_back_text TEXT,
    feed_forward_text TEXT
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
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        s.id,
        s.student_id,
        s.task_id,
        s.submission_data,
        s.submission_data::TEXT as submission_text,  -- For backwards compatibility
        s.is_correct,
        s.submitted_at as created_at,  -- Map to created_at for UI
        s.submitted_at,
        s.ai_feedback,
        s.feedback_generated_at as ai_feedback_generated_at,
        s.teacher_override_feedback as teacher_feedback,
        NULL::TIMESTAMPTZ as teacher_feedback_generated_at,  -- Column doesn't exist
        CASE WHEN s.teacher_override_grade IS NOT NULL THEN true ELSE false END as override_grade,
        s.feedback_viewed_at,
        s.attempt_number,  -- Include attempt_number!
        s.feedback_status,
        s.ai_grade,
        s.teacher_override_feedback,
        s.teacher_override_grade,
        s.feed_back_text,
        s.feed_forward_text
    FROM submission s
    WHERE s.student_id = p_student_id 
      AND s.task_id = p_task_id
      AND (
        -- Students can see their own history
        (v_user_role = 'student' AND s.student_id = v_user_id)
        OR
        -- Teachers can see history for tasks in their units  
        (v_user_role = 'teacher' AND EXISTS (
            SELECT 1
            FROM task_base tb
            JOIN unit_section us ON tb.section_id = us.id
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE tb.id = s.task_id 
              AND lu.creator_id = v_user_id
        ))
      )
    ORDER BY s.attempt_number;  -- Sort by attempt number
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_submission_history(TEXT, UUID, UUID) TO anon;