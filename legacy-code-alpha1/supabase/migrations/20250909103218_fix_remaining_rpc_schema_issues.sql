-- Fix remaining RPC schema issues identified in docker logs
-- Focus: get_section_statuses_for_unit_in_course, get_all_feedback  
-- Priority: CRITICAL - Fixes last 2 of 3 critical user problems

BEGIN;

-- =============================================================================
-- 1. Fix get_section_statuses_for_unit_in_course: created_by -> creator_id
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_section_statuses_for_unit_in_course(
    p_session_id TEXT,
    p_unit_id UUID,
    p_course_id UUID
)
RETURNS TABLE(
    section_id uuid,
    is_published boolean
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

    -- Authorization check (teachers only for this function)
    IF v_user_role != 'teacher' THEN
        RETURN;
    END IF;
    
    -- Check if teacher is authorized for this course  
    IF NOT EXISTS (
        SELECT 1 FROM course c 
        WHERE c.id = p_course_id 
        AND (c.creator_id = v_user_id OR EXISTS (  -- FIX: Use creator_id instead of created_by
            SELECT 1 FROM course_teacher ct 
            WHERE ct.course_id = p_course_id 
            AND ct.teacher_id = v_user_id
        ))
    ) THEN
        RETURN;
    END IF;

    -- Return section publication status
    RETURN QUERY
    SELECT 
        us.id as section_id,
        COALESCE(scp.is_published, FALSE) as is_published
    FROM unit_section us
    LEFT JOIN section_course_publication scp ON scp.section_id = us.id AND scp.course_id = p_course_id
    WHERE us.unit_id = p_unit_id
    ORDER BY us.order_in_unit;
END;
$$;

-- =============================================================================
-- 2. Fix get_all_feedback: Match actual feedback table schema
-- =============================================================================

DROP FUNCTION IF EXISTS public.get_all_feedback(TEXT);
CREATE FUNCTION public.get_all_feedback(
    p_session_id TEXT
)
RETURNS TABLE(
    id uuid,
    feedback_type text,
    message text,
    created_at timestamp with time zone
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

    -- Only teachers can see all feedback
    IF NOT v_is_valid OR v_user_role != 'teacher' THEN
        RETURN;
    END IF;

    -- Return all feedback using actual table schema
    RETURN QUERY
    SELECT
        f.id,
        f.feedback_type,
        f.message,
        f.created_at
    FROM feedback f
    ORDER BY f.created_at DESC;
END;
$$;

COMMIT;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.get_section_statuses_for_unit_in_course TO anon;
GRANT EXECUTE ON FUNCTION public.get_all_feedback TO anon;