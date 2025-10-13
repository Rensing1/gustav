-- Copyright (c) 2025 GUSTAV Contributors
-- SPDX-License-Identifier: MIT

-- Create auth_sessions table for HttpOnly cookie session management
-- This replaces Redis as session storage for pragmatic, simplified architecture

-- Create auth_sessions table if not exists
CREATE TABLE IF NOT EXISTS public.auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    user_role TEXT NOT NULL CHECK (user_role IN ('teacher', 'student', 'admin')),
    data JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    -- Add constraint to prevent extremely long sessions
    CONSTRAINT valid_expiration CHECK (expires_at <= created_at + INTERVAL '24 hours')
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_auth_sessions_session_id ON public.auth_sessions (session_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON public.auth_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON public.auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_last_activity ON public.auth_sessions (last_activity);

-- Enable Row Level Security
ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (safe for migrations)
DROP POLICY IF EXISTS "Service role full access" ON public.auth_sessions;
DROP POLICY IF EXISTS "Users can read own sessions" ON public.auth_sessions;

-- RLS Policies
-- Policy: Service role can do everything (for auth service)
CREATE POLICY "Service role full access" ON public.auth_sessions
    FOR ALL 
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Authenticated users can only read their own sessions
CREATE POLICY "Users can read own sessions" ON public.auth_sessions
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Function to cleanup expired sessions
CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.auth_sessions 
    WHERE expires_at < NOW()
    OR last_activity < NOW() - INTERVAL '90 minutes'; -- Also cleanup inactive sessions
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get session with activity update (atomic operation)
CREATE OR REPLACE FUNCTION public.get_session_with_activity_update(p_session_id VARCHAR(255))
RETURNS TABLE(
    id UUID,
    session_id VARCHAR(255),
    user_id UUID,
    user_email TEXT,
    user_role TEXT,
    data JSONB,
    expires_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT
) AS $$
BEGIN
    -- Update last_activity timestamp and extend expiration
    UPDATE public.auth_sessions
    SET 
        last_activity = NOW(),
        expires_at = GREATEST(expires_at, NOW() + INTERVAL '90 minutes')
    WHERE auth_sessions.session_id = p_session_id
    AND expires_at > NOW()
    AND last_activity > NOW() - INTERVAL '90 minutes';

    -- Return the updated session
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
    FROM public.auth_sessions s
    WHERE s.session_id = p_session_id
    AND s.expires_at > NOW()
    AND s.last_activity > NOW() - INTERVAL '90 minutes';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to limit sessions per user (prevent session flooding)
CREATE OR REPLACE FUNCTION public.enforce_session_limit()
RETURNS TRIGGER AS $$
DECLARE
    session_count INTEGER;
    max_sessions INTEGER := 5; -- Max 5 concurrent sessions per user
BEGIN
    -- Count current active sessions for this user
    SELECT COUNT(*) INTO session_count
    FROM public.auth_sessions
    WHERE user_id = NEW.user_id
    AND expires_at > NOW();

    -- If limit exceeded, delete oldest sessions
    IF session_count >= max_sessions THEN
        DELETE FROM public.auth_sessions
        WHERE user_id = NEW.user_id
        AND id IN (
            SELECT id FROM public.auth_sessions
            WHERE user_id = NEW.user_id
            ORDER BY last_activity ASC
            LIMIT (session_count - max_sessions + 1)
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for session limit enforcement
DROP TRIGGER IF EXISTS enforce_auth_session_limit ON public.auth_sessions;
CREATE TRIGGER enforce_auth_session_limit
    BEFORE INSERT ON public.auth_sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_session_limit();

-- Create a trigger to automatically update last_activity on any update
CREATE OR REPLACE FUNCTION public.update_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_auth_sessions_last_activity ON public.auth_sessions;
CREATE TRIGGER update_auth_sessions_last_activity
    BEFORE UPDATE ON public.auth_sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.update_last_activity();

-- Create cron job for automatic cleanup (requires pg_cron extension)
-- Note: This needs to be enabled in Supabase dashboard under Extensions
DO $$
BEGIN
    -- Check if pg_cron is available
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        -- Schedule cleanup every 15 minutes
        PERFORM cron.schedule(
            'cleanup-auth-sessions',
            '*/15 * * * *',
            'SELECT public.cleanup_expired_sessions();'
        );
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- pg_cron not available, manual cleanup needed
        RAISE NOTICE 'pg_cron not available. Manual session cleanup required.';
END;
$$;

-- Grant necessary permissions
GRANT ALL ON public.auth_sessions TO service_role;
GRANT SELECT ON public.auth_sessions TO authenticated;
GRANT EXECUTE ON FUNCTION public.cleanup_expired_sessions() TO service_role;
GRANT EXECUTE ON FUNCTION public.get_session_with_activity_update(VARCHAR) TO service_role;

-- Add helpful comments
COMMENT ON TABLE public.auth_sessions IS 'Stores active user sessions for HttpOnly cookie authentication';
COMMENT ON COLUMN public.auth_sessions.session_id IS 'Unique session identifier stored in HttpOnly cookie';
COMMENT ON COLUMN public.auth_sessions.user_role IS 'User role: teacher, student, or admin';
COMMENT ON COLUMN public.auth_sessions.data IS 'Additional session data in JSON format';
COMMENT ON COLUMN public.auth_sessions.expires_at IS 'Session expiration timestamp (max 24h from creation)';
COMMENT ON COLUMN public.auth_sessions.last_activity IS 'Last activity timestamp for sliding window timeout';
COMMENT ON COLUMN public.auth_sessions.ip_address IS 'Client IP address for security logging';
COMMENT ON COLUMN public.auth_sessions.user_agent IS 'Browser user agent for device tracking';
COMMENT ON FUNCTION public.cleanup_expired_sessions() IS 'Removes expired and inactive sessions - returns count of deleted sessions';
COMMENT ON FUNCTION public.get_session_with_activity_update(VARCHAR) IS 'Gets session and updates activity timestamp atomically with sliding window';
COMMENT ON FUNCTION public.enforce_session_limit() IS 'Limits concurrent sessions per user to prevent flooding';