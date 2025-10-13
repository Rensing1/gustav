-- CRITICAL FIX: Python code expects 'submission_text' in return values but gets 'submission_data'
-- Fix the RETURN TABLE schema to match what Python expects while converting JSONB to TEXT

-- Drop existing functions to allow schema changes
DROP FUNCTION IF EXISTS public.get_submission_by_id(TEXT, UUID);
DROP FUNCTION IF EXISTS public.get_submission_history(TEXT, UUID, UUID);

-- Fix get_submission_by_id function
CREATE OR REPLACE FUNCTION public.get_submission_by_id(
    p_session_id TEXT,
    p_submission_id UUID
)
RETURNS TABLE(
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_text TEXT,  -- Python expects this name
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    ai_feedback_generated_at TIMESTAMPTZ,
    teacher_feedback TEXT,
    teacher_feedback_generated_at TIMESTAMPTZ,
    override_grade BOOLEAN,
    feedback_viewed_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);

    IF NOT v_is_valid THEN
        RETURN;
    END IF;

    -- Return submission with JSONB converted to TEXT
    RETURN QUERY
    SELECT
        s.id,
        s.student_id,
        s.task_id,
        s.submission_data::TEXT as submission_text,  -- Convert JSONB to TEXT for Python
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        s.feedback_generated_at as ai_feedback_generated_at,
        s.teacher_override_feedback as teacher_feedback,
        NULL::TIMESTAMPTZ as teacher_feedback_generated_at,  -- Column doesn't exist
        CASE WHEN s.teacher_override_grade IS NOT NULL THEN true ELSE false END as override_grade,
        s.feedback_viewed_at
    FROM submission s
    WHERE s.id = p_submission_id
      AND (
        -- Students can see their own submissions
        (v_user_role = 'student' AND s.student_id = v_user_id)
        OR
        -- Teachers can see submissions for tasks in their units
        (v_user_role = 'teacher' AND EXISTS (
            SELECT 1
            FROM task_base tb
            JOIN unit_section us ON tb.section_id = us.id
            JOIN learning_unit lu ON us.unit_id = lu.id
            WHERE tb.id = s.task_id 
              AND lu.creator_id = v_user_id
        ))
      );
END;
$$;

-- Fix get_submission_history function  
CREATE OR REPLACE FUNCTION public.get_submission_history(
    p_session_id TEXT,
    p_student_id UUID,
    p_task_id UUID
)
RETURNS TABLE(
    id UUID,
    student_id UUID,
    task_id UUID,
    submission_text TEXT,  -- Python expects this name
    is_correct BOOLEAN,
    submitted_at TIMESTAMPTZ,
    ai_feedback TEXT,
    ai_feedback_generated_at TIMESTAMPTZ,
    teacher_feedback TEXT,
    teacher_feedback_generated_at TIMESTAMPTZ,
    override_grade BOOLEAN,
    feedback_viewed_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Session validieren
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
        s.submission_data::TEXT as submission_text,  -- Convert JSONB to TEXT for Python
        s.is_correct,
        s.submitted_at,
        s.ai_feedback,
        s.feedback_generated_at as ai_feedback_generated_at,
        s.teacher_override_feedback as teacher_feedback,
        NULL::TIMESTAMPTZ as teacher_feedback_generated_at,  -- Column doesn't exist
        CASE WHEN s.teacher_override_grade IS NOT NULL THEN true ELSE false END as override_grade,
        s.feedback_viewed_at
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
    ORDER BY s.submitted_at DESC;
END;
$$;