-- Fix submit_feedback function to use 'message' column instead of 'feedback_text'
-- This aligns with the existing UI implementation and table schema

CREATE OR REPLACE FUNCTION public.submit_feedback(
    p_session_id TEXT,
    p_page_identifier TEXT,
    p_feedback_type TEXT,
    p_feedback_text TEXT,
    p_sentiment TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id UUID;
    v_user_role TEXT;
    v_is_valid BOOLEAN;
    v_feedback_id UUID;
BEGIN
    -- Session validation (but allow anonymous feedback)
    SELECT user_id, user_role, is_valid
    INTO v_user_id, v_user_role, v_is_valid
    FROM public.validate_session_and_get_user(p_session_id);
    
    -- We allow anonymous feedback, so we don't check is_valid here
    
    -- Validate feedback type
    IF p_feedback_type NOT IN ('unterricht', 'plattform', 'bug') THEN
        RAISE EXCEPTION 'Invalid feedback type: %', p_feedback_type;
    END IF;
    
    -- Insert feedback (anonymous allowed)
    -- IMPORTANT: Use 'message' column to match the existing schema
    INSERT INTO feedback (
        page_identifier,
        feedback_type,
        message,           -- Changed from feedback_text to message
        feedback_text,     -- Also populate feedback_text for backwards compatibility
        sentiment,
        metadata,
        created_at
    )
    VALUES (
        p_page_identifier,
        p_feedback_type,
        p_feedback_text,   -- This goes into 'message' column (NOT NULL)
        p_feedback_text,   -- Also store in feedback_text for backwards compatibility
        p_sentiment,
        p_metadata,
        NOW()
    )
    RETURNING id INTO v_feedback_id;
    
    RETURN v_feedback_id;
END;
$$;

-- Ensure permissions remain the same
GRANT EXECUTE ON FUNCTION public.submit_feedback TO anon;