-- Storage RLS Migration for HttpOnly Cookie Authentication (Fixed Syntax)
-- This migration updates all storage policies to work with session-based auth
-- instead of relying on auth.uid()

-- ============================================
-- HELPER FUNCTION FOR STORAGE AUTHENTICATION
-- ============================================

-- Create a helper function to validate storage access via session
CREATE OR REPLACE FUNCTION public.validate_storage_session_user(path text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $function$
DECLARE
    v_session_id text;
    v_user_id uuid;
    v_is_valid boolean;
BEGIN
    -- Get session from cookie
    v_session_id := current_setting('request.cookies', true)::json->>'gustav_session';
    
    IF v_session_id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Validate session and get user
    SELECT user_id, is_valid
    INTO v_user_id, v_is_valid
    FROM public.validate_session_and_get_user(v_session_id);
    
    IF NOT v_is_valid THEN
        RETURN NULL;
    END IF;
    
    RETURN v_user_id;
END;
$function$;

-- ============================================
-- SUBMISSIONS BUCKET POLICIES
-- ============================================

-- Drop all existing submissions policies
DROP POLICY IF EXISTS "Users can upload own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can view own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Teachers can view student submission files" ON storage.objects;
DROP POLICY IF EXISTS "submissions_insert_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_select_policy" ON storage.objects;

-- Create new policies using session validation

-- Students can upload their own submissions
CREATE POLICY "submissions_insert_session_policy" ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = 'submissions' AND
    -- Path must be: student_{user_id}/...
    (storage.foldername(name))[1] = concat('student_', validate_storage_session_user(name)::text)
);

-- Students can view their own submissions
CREATE POLICY "submissions_select_session_policy" ON storage.objects
FOR SELECT TO authenticated
USING (
    bucket_id = 'submissions' AND
    (
        -- Students can see their own files
        (storage.foldername(name))[1] = concat('student_', validate_storage_session_user(name)::text)
        OR
        -- Teachers can see submissions for their courses
        EXISTS (
            SELECT 1
            FROM validate_session_and_get_user(
                current_setting('request.cookies', true)::json->>'gustav_session'
            ) AS auth_check
            WHERE auth_check.is_valid 
            AND auth_check.user_role = 'teacher'
            AND EXISTS (
                -- Extract student_id and task_id from path
                SELECT 1
                FROM course c
                JOIN course_learning_unit_assignment cla ON cla.course_id = c.id
                JOIN learning_unit lu ON lu.id = cla.unit_id
                JOIN unit_section us ON us.unit_id = lu.id
                JOIN task_base tb ON tb.section_id = us.id
                WHERE c.creator_id = auth_check.user_id
                AND tb.id::text = split_part((storage.foldername(name))[2], '_', 2)
            )
        )
    )
);

-- Students can delete their own submissions (if needed)
CREATE POLICY "submissions_delete_session_policy" ON storage.objects
FOR DELETE TO authenticated
USING (
    bucket_id = 'submissions' AND
    (storage.foldername(name))[1] = concat('student_', validate_storage_session_user(name)::text)
);

-- ============================================
-- MATERIALS BUCKET POLICIES (if still in use)
-- ============================================

-- Drop old policies that use auth.uid()
DROP POLICY IF EXISTS "Allow teachers to upload based on owner role" ON storage.objects;
DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to update materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to delete materials" ON storage.objects;

-- Create new session-based policies for materials bucket
CREATE POLICY "materials_insert_session_policy" ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = 'materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
    )
);

CREATE POLICY "materials_update_session_policy" ON storage.objects
FOR UPDATE TO authenticated
USING (
    bucket_id = 'materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
    )
)
WITH CHECK (
    bucket_id = 'materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
    )
);

CREATE POLICY "materials_delete_session_policy" ON storage.objects
FOR DELETE TO authenticated
USING (
    bucket_id = 'materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
    )
);

-- ============================================
-- SECTION_MATERIALS BUCKET
-- ============================================

-- Note: section_materials already has public read policy (no auth required)
-- We only need to update write policies that might still use auth.uid()

DROP POLICY IF EXISTS "allow_insert_for_unit_creators" ON storage.objects;
DROP POLICY IF EXISTS "allow_update_for_unit_creators" ON storage.objects;
DROP POLICY IF EXISTS "allow_delete_for_unit_creators" ON storage.objects;

-- Teachers can manage section materials for units they created
CREATE POLICY "section_materials_insert_session_policy" ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = 'section_materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
        AND is_creator_of_unit(auth_check.user_id, get_unit_id_from_path(name))
    )
);

CREATE POLICY "section_materials_update_session_policy" ON storage.objects
FOR UPDATE TO authenticated
USING (
    bucket_id = 'section_materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
        AND is_creator_of_unit(auth_check.user_id, get_unit_id_from_path(name))
    )
)
WITH CHECK (
    bucket_id = 'section_materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
        AND is_creator_of_unit(auth_check.user_id, get_unit_id_from_path(name))
    )
);

CREATE POLICY "section_materials_delete_session_policy" ON storage.objects
FOR DELETE TO authenticated
USING (
    bucket_id = 'section_materials' AND
    EXISTS (
        SELECT 1
        FROM validate_session_and_get_user(
            current_setting('request.cookies', true)::json->>'gustav_session'
        ) AS auth_check
        WHERE auth_check.is_valid 
        AND auth_check.user_role = 'teacher'
        AND is_creator_of_unit(auth_check.user_id, get_unit_id_from_path(name))
    )
);

-- ============================================
-- GRANT PERMISSIONS
-- ============================================

-- Ensure the helper function can be used by authenticated users
GRANT EXECUTE ON FUNCTION public.validate_storage_session_user TO authenticated;
GRANT EXECUTE ON FUNCTION public.validate_storage_session_user TO anon;