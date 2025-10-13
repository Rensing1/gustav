-- Fix the get_user_profile_for_auth function to match the actual table structure
-- The role column is of type user_role, not text

-- Drop the existing function
DROP FUNCTION IF EXISTS public.get_user_profile_for_auth(UUID);

-- Recreate with correct return types
CREATE OR REPLACE FUNCTION public.get_user_profile_for_auth(p_user_id UUID)
RETURNS TABLE(
    id UUID,
    role user_role,  -- Changed from TEXT to user_role
    email TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) 
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Return profile data for the given user
    RETURN QUERY
    SELECT 
        p.id,
        p.role,
        p.email,
        p.created_at,
        p.updated_at
    FROM public.profiles p
    WHERE p.id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission to anon role (used by auth service)
GRANT EXECUTE ON FUNCTION public.get_user_profile_for_auth(UUID) TO anon;

-- Update comment
COMMENT ON FUNCTION public.get_user_profile_for_auth(UUID) IS 
'Fetches user profile for authentication service. Uses SECURITY DEFINER to bypass RLS when called with anon key. Fixed to return user_role type.';