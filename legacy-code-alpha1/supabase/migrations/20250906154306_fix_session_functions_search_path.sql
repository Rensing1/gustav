-- Fix search_path for session functions to include extensions schema
-- This fixes the "function gen_random_bytes(integer) does not exist" error

-- Update search_path for create_session function
ALTER FUNCTION public.create_session(UUID, TEXT, TEXT, JSONB, INTERVAL, INET, TEXT) 
SET search_path = public, extensions;

-- Update search_path for other session functions that might need it
ALTER FUNCTION public.get_session(VARCHAR) 
SET search_path = public, extensions;

ALTER FUNCTION public.validate_session(VARCHAR) 
SET search_path = public, extensions;

ALTER FUNCTION public.update_session(VARCHAR, JSONB) 
SET search_path = public, extensions;

ALTER FUNCTION public.delete_session(VARCHAR) 
SET search_path = public, extensions;

ALTER FUNCTION public.cleanup_expired_sessions() 
SET search_path = public, extensions;

-- Ensure all functions have proper access to extensions
GRANT EXECUTE ON FUNCTION extensions.gen_random_bytes(integer) TO authenticator;
GRANT EXECUTE ON FUNCTION extensions.gen_random_bytes(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION extensions.gen_random_bytes(integer) TO anon;

-- Test that gen_random_bytes is accessible
DO $$
BEGIN
    PERFORM extensions.gen_random_bytes(32);
    RAISE NOTICE 'gen_random_bytes is accessible';
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'gen_random_bytes is not accessible: %', SQLERRM;
END $$;