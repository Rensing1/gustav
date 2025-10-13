-- Fix MAX(uuid) error in get_published_section_details_for_student
-- PostgreSQL doesn't support MAX() on UUID columns

-- Drop the problematic 4-parameter function that contains MAX(sub.id) 
DROP FUNCTION IF EXISTS public.get_published_section_details_for_student(TEXT, UUID, UUID, UUID);

-- Keep only the 2-parameter function that works correctly
-- The 4-parameter version can be replaced with separate calls if needed