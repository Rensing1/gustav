-- Migration: Fix user_roles table references
-- Purpose: Replace user_roles table checks with validate_session_and_get_user function calls

-- Fix get_submission_by_id to use session validation properly
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
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_student_id UUID;
BEGIN
    -- Get user from session with role
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session';
    END IF;
    
    -- Get student_id from submission
    SELECT s.student_id INTO v_student_id
    FROM submission s
    WHERE s.id = p_submission_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submission not found';
    END IF;
    
    -- Authorization: student can view own submissions, teachers can view all
    IF v_user_id != v_student_id AND v_user_role != 'teacher' THEN
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

-- Remove the backward compatibility wrapper for get_mastery_summary that requires service role
DROP FUNCTION IF EXISTS get_mastery_summary(UUID, UUID);

-- Ensure all mastery functions accept session_id properly
-- The functions should already be updated, just ensure permissions
GRANT EXECUTE ON FUNCTION get_submission_by_id TO authenticated;
GRANT EXECUTE ON FUNCTION get_mastery_summary TO authenticated;
GRANT EXECUTE ON FUNCTION get_mastery_stats_for_student TO authenticated;
GRANT EXECUTE ON FUNCTION get_due_tomorrow_count TO authenticated;