-- SECURITY FIX: Restore secure RLS policies for submissions bucket
-- Datum: 2025-08-27
-- Zweck: Ersetzt unsichere "allow all" Policy durch korrekte User-Isolation

-- 1. Entferne die unsichere temporaere Policy
DROP POLICY IF EXISTS "temp_submissions_allow_all" ON storage.objects;

-- 2. Erstelle sichere RLS Policies

-- Policy: Schueler koennen nur ihre eigenen Dateien hochladen
-- Pfad-Format erwartet: student_{user_id}/task_{task_id}/filename
CREATE POLICY "submissions_insert_policy" 
ON storage.objects FOR INSERT 
TO authenticated
WITH CHECK (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = CONCAT('student_', auth.uid()::text)
);

-- Policy: Schueler koennen nur ihre eigenen Dateien lesen
CREATE POLICY "submissions_select_policy"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = CONCAT('student_', auth.uid()::text)
);

-- Sicherheitsnotiz:
-- - Pfad-Format ist jetzt: student_{uuid}/task_{task_id}/filename
-- - Nur der User selbst kann seine Dateien sehen
-- - Lehrer-Policies werden in separater Migration implementiert
-- - Keine Loeschung/Aenderung moeglich (Audit-Trail)