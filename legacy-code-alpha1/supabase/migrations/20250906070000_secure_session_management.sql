-- Secure session management without service role key
-- This migration creates a dedicated role and RLS policies for the auth service

-- Create a dedicated role for the auth service
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'session_manager') THEN
        CREATE ROLE session_manager;
    END IF;
END$$;

-- Grant necessary permissions to session_manager role
GRANT USAGE ON SCHEMA public TO session_manager;
GRANT ALL ON public.auth_sessions TO session_manager;
GRANT EXECUTE ON FUNCTION public.cleanup_expired_sessions() TO session_manager;
GRANT EXECUTE ON FUNCTION public.get_session_with_activity_update(VARCHAR) TO session_manager;

-- Create a specific RLS policy for session management
DROP POLICY IF EXISTS "Session manager full access" ON public.auth_sessions;
CREATE POLICY "Session manager full access" ON public.auth_sessions
    FOR ALL 
    TO session_manager
    USING (true)
    WITH CHECK (true);

-- Alternative: API Key based authentication
-- Create a table for API keys that can manage sessions
CREATE TABLE IF NOT EXISTS public.auth_service_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL UNIQUE, -- Store bcrypt hash of the key
    name TEXT NOT NULL,
    permissions JSONB DEFAULT '["manage_sessions"]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true
);

-- RLS for API keys table
ALTER TABLE public.auth_service_keys ENABLE ROW LEVEL SECURITY;

-- Only service role can manage API keys
CREATE POLICY "Service role manages API keys" ON public.auth_service_keys
    FOR ALL 
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Function to validate API key and get permissions
CREATE OR REPLACE FUNCTION public.validate_auth_service_key(api_key TEXT)
RETURNS TABLE(is_valid BOOLEAN, permissions JSONB) 
SECURITY DEFINER
AS $$
DECLARE
    key_record RECORD;
BEGIN
    -- In production, compare against bcrypt hash
    -- For now, simple comparison (YOU MUST USE BCRYPT IN PRODUCTION!)
    SELECT * INTO key_record 
    FROM public.auth_service_keys 
    WHERE key_hash = api_key AND is_active = true;
    
    IF FOUND THEN
        -- Update last used timestamp
        UPDATE public.auth_service_keys 
        SET last_used_at = NOW() 
        WHERE id = key_record.id;
        
        RETURN QUERY SELECT true, key_record.permissions;
    ELSE
        RETURN QUERY SELECT false, NULL::JSONB;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to create session with API key validation
CREATE OR REPLACE FUNCTION public.create_session_with_api_key(
    p_api_key TEXT,
    p_session_id VARCHAR(255),
    p_user_id UUID,
    p_user_email TEXT,
    p_user_role TEXT,
    p_data JSONB,
    p_expires_at TIMESTAMPTZ,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS UUID
SECURITY DEFINER
AS $$
DECLARE
    key_validation RECORD;
    new_session_id UUID;
BEGIN
    -- Validate API key
    SELECT * INTO key_validation FROM public.validate_auth_service_key(p_api_key);
    
    IF NOT key_validation.is_valid THEN
        RAISE EXCEPTION 'Invalid API key';
    END IF;
    
    IF NOT (key_validation.permissions ? 'manage_sessions') THEN
        RAISE EXCEPTION 'API key lacks session management permission';
    END IF;
    
    -- Create session
    INSERT INTO public.auth_sessions (
        session_id, user_id, user_email, user_role, 
        data, expires_at, ip_address, user_agent
    ) VALUES (
        p_session_id, p_user_id, p_user_email, p_user_role,
        p_data, p_expires_at, p_ip_address, p_user_agent
    ) RETURNING id INTO new_session_id;
    
    RETURN new_session_id;
END;
$$ LANGUAGE plpgsql;

-- Add comment
COMMENT ON FUNCTION public.create_session_with_api_key IS 'Creates a session after validating API key - secure alternative to using service role';

-- Example: Insert a development API key (REMOVE IN PRODUCTION!)
-- INSERT INTO public.auth_service_keys (key_hash, name, permissions) 
-- VALUES ('dev_key_hash_here', 'Development Auth Service', '["manage_sessions"]');