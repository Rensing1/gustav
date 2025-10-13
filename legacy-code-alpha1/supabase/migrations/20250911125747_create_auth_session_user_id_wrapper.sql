-- Migration: Create session_user_id wrapper function
-- Purpose: Provide a simple wrapper to get user_id from session for consistency

-- Create the wrapper function in public schema but name it to match expected auth.session_user_id
CREATE OR REPLACE FUNCTION public.session_user_id(p_session_id TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
BEGIN
    -- Use the existing validate_session_and_get_user function
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    -- Return NULL if session is invalid
    IF NOT v_is_valid OR v_user_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    RETURN v_user_id;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.session_user_id TO authenticated;

-- Add comment
COMMENT ON FUNCTION public.session_user_id IS 'Simple wrapper to get user_id from session_id for consistency across RPC functions';

-- Also fix the parameter order issue by creating an overloaded version of get_mastery_summary
-- that accepts parameters in the old order for backward compatibility
CREATE OR REPLACE FUNCTION get_mastery_summary(
    p_student_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    total INT,
    mastered INT,
    learning INT,
    not_started INT,
    due_today INT,
    avg_stability FLOAT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    -- This is a compatibility wrapper that calls the new version with a dummy session
    -- It should only be used by the worker which has service role access
    -- For security, we check if this is being called from a service context
    IF current_setting('request.jwt.claims', true)::json->>'role' != 'service_role' THEN
        RAISE EXCEPTION 'This function requires service role access';
    END IF;
    
    -- Return the actual data without session validation since service role is trusted
    RETURN QUERY
    WITH task_stats AS (
        SELECT
            mt.id,
            CASE
                WHEN smp.stability > 21 THEN 'mastered'
                WHEN smp.stability IS NOT NULL THEN 'learning'
                ELSE 'not_started'
            END as status,
            smp.stability,
            smp.next_due_date
        FROM mastery_tasks mt
        JOIN unit_section us ON us.id = mt.section_id
        JOIN course_units cu ON cu.unit_id = us.unit_id
        LEFT JOIN student_mastery_progress smp ON smp.task_id = mt.id 
            AND smp.student_id = p_student_id
        WHERE cu.course_id = p_course_id
    )
    SELECT
        COUNT(*)::INT as total,
        COUNT(CASE WHEN status = 'mastered' THEN 1 END)::INT as mastered,
        COUNT(CASE WHEN status = 'learning' THEN 1 END)::INT as learning,
        COUNT(CASE WHEN status = 'not_started' THEN 1 END)::INT as not_started,
        COUNT(CASE WHEN next_due_date <= CURRENT_DATE THEN 1 END)::INT as due_today,
        COALESCE(AVG(stability), 1.0)::FLOAT as avg_stability
    FROM task_stats;
END;
$$;

GRANT EXECUTE ON FUNCTION get_mastery_summary(UUID, UUID) TO authenticated;
COMMENT ON FUNCTION get_mastery_summary(UUID, UUID) IS 'Backward compatibility wrapper for old parameter order (service role only)';