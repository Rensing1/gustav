-- Fix: Create a secure session creation function for the auth service
-- This function can be called by anon but requires validation

-- Drop the old function if it exists
DROP FUNCTION IF EXISTS create_session_for_auth_service(UUID, TEXT, TEXT, JSONB, INTERVAL, INET, TEXT);

-- Create the new function that anon can use
CREATE OR REPLACE FUNCTION create_session_for_auth_service(
    p_user_id UUID,
    p_user_email TEXT,
    p_user_role TEXT,
    p_data JSONB DEFAULT '{}',
    p_expires_in INTERVAL DEFAULT INTERVAL '90 minutes',
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS VARCHAR -- Returns session_id directly
SECURITY DEFINER
SET search_path = public, extensions
LANGUAGE plpgsql
AS $$
DECLARE
    v_session_id VARCHAR(255);
    v_user RECORD;
    v_result RECORD;
BEGIN
    -- SECURITY: Validate that the user actually exists and email matches
    SELECT id, email INTO v_user
    FROM auth.users 
    WHERE id = p_user_id;
    
    IF v_user.id IS NULL THEN
        RAISE EXCEPTION 'Invalid user_id';
    END IF;
    
    -- SECURITY: Verify email matches (case-insensitive)
    IF lower(v_user.email) != lower(p_user_email) THEN
        RAISE EXCEPTION 'Email mismatch for user';
    END IF;
    
    -- Call the existing create_session function with elevated privileges
    SELECT session_id INTO v_session_id
    FROM create_session(
        p_user_id,
        p_user_email,
        p_user_role,
        p_data,
        p_expires_in,
        p_ip_address,
        p_user_agent
    );
    
    RETURN v_session_id;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error but don't expose internal details
        RAISE LOG 'Session creation error: %', SQLERRM;
        RAISE EXCEPTION 'Failed to create session';
END;
$$;

-- Grant execute permission to anon (auth service uses anon key)
GRANT EXECUTE ON FUNCTION create_session_for_auth_service(UUID, TEXT, TEXT, JSONB, INTERVAL, INET, TEXT) TO anon;

-- Add documentation
COMMENT ON FUNCTION create_session_for_auth_service IS 'Secure session creation for auth service - validates user exists and email matches before creating session';