-- Migration: Update get_submission_by_id to include feedback_status and new feedback fields
-- Purpose: Fix UI not showing feedback because missing fields in RPC response

DROP FUNCTION IF EXISTS get_submission_by_id(TEXT, UUID);

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

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_submission_by_id TO authenticated;

-- Add comment
COMMENT ON FUNCTION get_submission_by_id IS 'Gets submission details including feedback status and all feedback fields';