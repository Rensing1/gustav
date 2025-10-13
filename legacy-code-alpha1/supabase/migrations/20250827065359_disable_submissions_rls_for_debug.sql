-- TEMPORARY DEBUG Migration: Disable RLS on submissions bucket
-- Datum: 2025-08-27
-- Zweck: Temporaer RLS auf submissions bucket deaktivieren um Upload zu testen

-- Entferne alle submissions storage policies temporaer
DROP POLICY IF EXISTS "submissions_insert_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_select_policy" ON storage.objects;  
DROP POLICY IF EXISTS "submissions_update_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_delete_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_teacher_view_policy" ON storage.objects;

-- Erstelle temporaere, sehr permissive Policy nur fuer submissions bucket
CREATE POLICY "temp_submissions_allow_all"
ON storage.objects FOR ALL 
TO authenticated
USING (bucket_id = 'submissions')
WITH CHECK (bucket_id = 'submissions');

-- Notiz: Diese Migration ist nur fuer Debugging gedacht
-- TODO: Spaeter wieder mit korrekten RLS Policies ersetzen