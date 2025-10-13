-- Copyright (c) 2025 GUSTAV Contributors
-- SPDX-License-Identifier: MIT

-- SQL Function to fetch user profile for auth service
-- Uses SECURITY DEFINER to bypass RLS when called with anon key

-- Drop existing function if exists
DROP FUNCTION IF EXISTS public.get_user_profile_for_auth(UUID);

-- Create function to get user profile
CREATE OR REPLACE FUNCTION public.get_user_profile_for_auth(p_user_id UUID)
RETURNS TABLE(
    id UUID,
    role TEXT,
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
    
    -- If no profile found, return empty result
    -- The auth service will handle this appropriately
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission to anon role (used by auth service)
GRANT EXECUTE ON FUNCTION public.get_user_profile_for_auth(UUID) TO anon;

-- Add helpful comment
COMMENT ON FUNCTION public.get_user_profile_for_auth(UUID) IS 
'Fetches user profile for authentication service. Uses SECURITY DEFINER to bypass RLS when called with anon key.';