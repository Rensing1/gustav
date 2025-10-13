-- Secure session management functions with SECURITY DEFINER
-- These functions run with elevated privileges but expose only safe operations
-- No service role key needed in the application!

-- Drop existing functions if they exist (for idempotency)
DROP FUNCTION IF EXISTS create_session(UUID, TEXT, TEXT, JSONB, INTERVAL, INET, TEXT);
DROP FUNCTION IF EXISTS get_session(VARCHAR);
DROP FUNCTION IF EXISTS update_session(VARCHAR, JSONB);
DROP FUNCTION IF EXISTS delete_session(VARCHAR);
DROP FUNCTION IF EXISTS get_user_sessions(UUID);
DROP FUNCTION IF EXISTS invalidate_user_sessions(UUID);
DROP FUNCTION IF EXISTS validate_session(VARCHAR);

-- =============================================================================
-- RATE LIMITING TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.session_rate_limits (
    user_id UUID PRIMARY KEY,
    attempts INT DEFAULT 1,
    window_start TIMESTAMPTZ DEFAULT NOW(),
    last_attempt TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_session_rate_limits_window 
ON session_rate_limits(window_start);

-- Cleanup function for old rate limit entries
CREATE OR REPLACE FUNCTION cleanup_session_rate_limits()
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM session_rate_limits 
    WHERE window_start < NOW() - INTERVAL '1 hour';
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

-- =============================================================================
-- CREATE SESSION
-- =============================================================================
CREATE OR REPLACE FUNCTION create_session(
    p_user_id UUID,
    p_user_email TEXT,
    p_user_role TEXT,
    p_data JSONB DEFAULT '{}',
    p_expires_in INTERVAL DEFAULT INTERVAL '90 minutes',
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS TABLE(
    session_id VARCHAR,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_session_id VARCHAR(255);
    v_expires_at TIMESTAMPTZ;
    v_created_at TIMESTAMPTZ;
    v_session_count INT;
    v_rate_limit RECORD;
BEGIN
    -- Rate limiting check
    INSERT INTO session_rate_limits (user_id, attempts, window_start, last_attempt)
    VALUES (p_user_id, 1, NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE
    SET 
        attempts = CASE 
            WHEN session_rate_limits.window_start < NOW() - INTERVAL '1 hour' THEN 1
            ELSE session_rate_limits.attempts + 1
        END,
        window_start = CASE 
            WHEN session_rate_limits.window_start < NOW() - INTERVAL '1 hour' THEN NOW()
            ELSE session_rate_limits.window_start
        END,
        last_attempt = NOW()
    RETURNING * INTO v_rate_limit;
    
    -- Check rate limit (max 10 attempts per hour)
    IF v_rate_limit.window_start > NOW() - INTERVAL '1 hour' AND v_rate_limit.attempts > 10 THEN
        RAISE EXCEPTION 'Rate limit exceeded. Too many session creation attempts.';
    END IF;
    
    -- Clean up old rate limits periodically
    IF random() < 0.01 THEN -- 1% chance to run cleanup
        PERFORM cleanup_session_rate_limits();
    END IF;
    
    -- Validate inputs
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'user_id cannot be null';
    END IF;
    
    IF p_user_email IS NULL OR p_user_email = '' THEN
        RAISE EXCEPTION 'user_email cannot be empty';
    END IF;
    
    IF p_user_role NOT IN ('teacher', 'student', 'admin') THEN
        RAISE EXCEPTION 'Invalid user_role: %', p_user_role;
    END IF;
    
    -- Check if user exists in auth.users
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id) THEN
        RAISE EXCEPTION 'User % does not exist', p_user_id;
    END IF;
    
    -- Generate secure session ID
    v_session_id := encode(gen_random_bytes(32), 'base64');
    v_session_id := replace(v_session_id, '+', '-');
    v_session_id := replace(v_session_id, '/', '_');
    v_session_id := rtrim(v_session_id, '=');
    
    -- Calculate expiration
    v_expires_at := NOW() + p_expires_in;
    v_created_at := NOW();
    
    -- Insert new session (trigger will handle session limit)
    INSERT INTO auth_sessions (
        session_id,
        user_id,
        user_email,
        user_role,
        data,
        expires_at,
        ip_address,
        user_agent,
        created_at,
        last_activity
    ) VALUES (
        v_session_id,
        p_user_id,
        p_user_email,
        p_user_role,
        p_data,
        v_expires_at,
        p_ip_address,
        p_user_agent,
        v_created_at,
        v_created_at
    );
    
    -- Log session creation
    RAISE LOG 'Session created for user % with role %', p_user_id, p_user_role;
    
    RETURN QUERY SELECT v_session_id, v_expires_at, v_created_at;
END;
$$;

-- =============================================================================
-- GET SESSION (with activity update)
-- =============================================================================
CREATE OR REPLACE FUNCTION get_session(p_session_id VARCHAR)
RETURNS TABLE(
    id UUID,
    session_id VARCHAR,
    user_id UUID,
    user_email TEXT,
    user_role TEXT,
    data JSONB,
    expires_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    -- Update last_activity if session exists and not expired
    UPDATE auth_sessions s
    SET last_activity = NOW()
    WHERE s.session_id = p_session_id
      AND s.expires_at > NOW();
    
    -- Return session data
    RETURN QUERY
    SELECT 
        s.id,
        s.session_id,
        s.user_id,
        s.user_email,
        s.user_role,
        s.data,
        s.expires_at,
        s.last_activity,
        s.created_at,
        s.ip_address,
        s.user_agent
    FROM auth_sessions s
    WHERE s.session_id = p_session_id
      AND s.expires_at > NOW();
END;
$$;

-- =============================================================================
-- VALIDATE SESSION (for nginx auth_request)
-- =============================================================================
CREATE OR REPLACE FUNCTION validate_session(p_session_id VARCHAR)
RETURNS TABLE(
    is_valid BOOLEAN,
    user_id UUID,
    user_email TEXT,
    user_role TEXT,
    expires_in_seconds INT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_session RECORD;
BEGIN
    -- Optimized: Update activity and get session in one query
    WITH updated AS (
        UPDATE auth_sessions s
        SET last_activity = NOW()
        WHERE s.session_id = p_session_id
          AND s.expires_at > NOW()
        RETURNING s.*
    )
    SELECT * INTO v_session FROM updated;
    
    IF v_session.id IS NULL THEN
        RETURN QUERY SELECT 
            false::BOOLEAN,
            NULL::UUID,
            NULL::TEXT,
            NULL::TEXT,
            0::INT;
    ELSE
        RETURN QUERY SELECT
            true::BOOLEAN,
            v_session.user_id,
            v_session.user_email,
            v_session.user_role,
            EXTRACT(EPOCH FROM (v_session.expires_at - NOW()))::INT;
    END IF;
END;
$$;

-- =============================================================================
-- UPDATE SESSION DATA
-- =============================================================================
CREATE OR REPLACE FUNCTION update_session(
    p_session_id VARCHAR,
    p_data JSONB
)
RETURNS BOOLEAN
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INT;
BEGIN
    UPDATE auth_sessions
    SET 
        data = p_data,
        last_activity = NOW()
    WHERE session_id = p_session_id
      AND expires_at > NOW();
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    
    RETURN v_updated > 0;
END;
$$;

-- =============================================================================
-- DELETE SESSION
-- =============================================================================
CREATE OR REPLACE FUNCTION delete_session(p_session_id VARCHAR)
RETURNS BOOLEAN
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM auth_sessions
    WHERE session_id = p_session_id;
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    
    IF v_deleted > 0 THEN
        RAISE LOG 'Session % deleted', p_session_id;
    END IF;
    
    RETURN v_deleted > 0;
END;
$$;

-- =============================================================================
-- GET USER SESSIONS
-- =============================================================================
CREATE OR REPLACE FUNCTION get_user_sessions(p_user_id UUID)
RETURNS TABLE(
    id UUID,
    session_id VARCHAR,
    user_email TEXT,
    user_role TEXT,
    expires_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.session_id,
        s.user_email,
        s.user_role,
        s.expires_at,
        s.last_activity,
        s.created_at,
        s.ip_address,
        s.user_agent
    FROM auth_sessions s
    WHERE s.user_id = p_user_id
      AND s.expires_at > NOW()
    ORDER BY s.last_activity DESC;
END;
$$;

-- =============================================================================
-- INVALIDATE ALL USER SESSIONS
-- =============================================================================
CREATE OR REPLACE FUNCTION invalidate_user_sessions(p_user_id UUID)
RETURNS INT
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM auth_sessions
    WHERE user_id = p_user_id;
    
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    
    IF v_deleted > 0 THEN
        RAISE LOG 'Invalidated % sessions for user %', v_deleted, p_user_id;
    END IF;
    
    RETURN v_deleted;
END;
$$;

-- =============================================================================
-- REFRESH SESSION (extend expiration)
-- =============================================================================
CREATE OR REPLACE FUNCTION refresh_session(
    p_session_id VARCHAR,
    p_extend_by INTERVAL DEFAULT INTERVAL '90 minutes'
)
RETURNS TIMESTAMPTZ
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    v_new_expiry TIMESTAMPTZ;
BEGIN
    UPDATE auth_sessions
    SET 
        expires_at = NOW() + p_extend_by,
        last_activity = NOW()
    WHERE session_id = p_session_id
      AND expires_at > NOW()
    RETURNING expires_at INTO v_new_expiry;
    
    IF v_new_expiry IS NULL THEN
        RAISE EXCEPTION 'Session % not found or expired', p_session_id;
    END IF;
    
    RETURN v_new_expiry;
END;
$$;

-- =============================================================================
-- GRANT PERMISSIONS
-- =============================================================================
-- SECURITY: Only grant necessary permissions
-- validate_session and get_session need anon access for auth checks
GRANT EXECUTE ON FUNCTION validate_session(VARCHAR) TO authenticated, anon;
GRANT EXECUTE ON FUNCTION get_session(VARCHAR) TO authenticated, anon;

-- All other functions require authentication
GRANT EXECUTE ON FUNCTION create_session(UUID, TEXT, TEXT, JSONB, INTERVAL, INET, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION update_session(VARCHAR, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION delete_session(VARCHAR) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_sessions(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION invalidate_user_sessions(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION refresh_session(VARCHAR, INTERVAL) TO authenticated;

-- =============================================================================
-- FUNCTION DOCUMENTATION
-- =============================================================================
COMMENT ON FUNCTION create_session IS 'Creates a new session for a user with automatic session limit enforcement';
COMMENT ON FUNCTION get_session IS 'Retrieves session data and updates last activity timestamp';
COMMENT ON FUNCTION validate_session IS 'Validates a session for nginx auth_request, returns user info if valid';
COMMENT ON FUNCTION update_session IS 'Updates session data (typically for storing additional metadata)';
COMMENT ON FUNCTION delete_session IS 'Explicitly deletes a session (logout)';
COMMENT ON FUNCTION get_user_sessions IS 'Gets all active sessions for a user';
COMMENT ON FUNCTION invalidate_user_sessions IS 'Deletes all sessions for a user (force logout everywhere)';
COMMENT ON FUNCTION refresh_session IS 'Extends session expiration time';

-- Note: Test functions should be in separate test migrations or test suites,
-- not in production migrations