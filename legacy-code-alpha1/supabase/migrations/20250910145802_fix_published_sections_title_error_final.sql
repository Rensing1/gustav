-- Fix published sections title error by removing old 2-parameter version

-- Drop the old 2-parameter version that has the t.title error
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID);

-- The correct 4-parameter version already exists and is being used now