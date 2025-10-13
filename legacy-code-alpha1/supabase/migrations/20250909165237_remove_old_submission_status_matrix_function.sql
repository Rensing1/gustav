-- Remove old version of _get_submission_status_matrix_uncached function to resolve overloading conflict
-- Keep only the newer version with the correct structure

DROP FUNCTION IF EXISTS public._get_submission_status_matrix_uncached(p_session_id text, p_course_id uuid, p_unit_id uuid);