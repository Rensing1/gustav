-- Migration: Rollback File Upload Feature
-- Datum: 2025-08-27
-- Zweck: Vollstaendiges Entfernen des File-Upload Features aus dem GUSTAV-System

-- 1. Entferne alle Storage Policies fuer submissions bucket
DROP POLICY IF EXISTS "temp_submissions_allow_all" ON storage.objects;
DROP POLICY IF EXISTS "submissions_insert_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_select_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_update_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_delete_policy" ON storage.objects;
DROP POLICY IF EXISTS "submissions_teacher_view_policy" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can view own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can update own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Teachers can view student submission files" ON storage.objects;

-- 2. Loesche alle Objekte im submissions Bucket, dann den Bucket selbst
DELETE FROM storage.objects WHERE bucket_id = 'submissions';
DELETE FROM storage.buckets WHERE id = 'submissions';

-- 3. Entferne Indizes fuer File-Upload
DROP INDEX IF EXISTS idx_submission_processing;
DROP INDEX IF EXISTS idx_submission_type_created;

-- 4. Sichere existierende File-Upload Daten (optional, fuer spaeteren Zugriff)
-- CREATE TABLE IF NOT EXISTS _backup_file_submissions AS
-- SELECT id, student_id, task_id, submission_type, file_path, original_filename, 
--        extracted_text, processing_stage, created_at
-- FROM submission
-- WHERE submission_type = 'file_upload';

-- 5. Setze alle File-Upload-Submissions auf Text zurueck (Behalte extrahierten Text)
UPDATE submission
SET submission_data = jsonb_build_object('text', COALESCE(extracted_text, '[Datei-Upload wurde entfernt]'))
WHERE submission_type = 'file_upload' 
  AND extracted_text IS NOT NULL;

-- 6. Entferne die File-Upload-bezogenen Spalten aus submission Tabelle
ALTER TABLE submission 
DROP COLUMN IF EXISTS submission_type,
DROP COLUMN IF EXISTS file_path,
DROP COLUMN IF EXISTS original_filename,
DROP COLUMN IF EXISTS extracted_text,
DROP COLUMN IF EXISTS processing_stage;

-- 7. Entferne Kommentare
-- (Kommentare werden automatisch mit den Spalten entfernt)

-- Verifikation: Pruefe, dass keine File-Upload-Referenzen mehr existieren
-- SELECT count(*) FROM submission WHERE submission_type = 'file_upload'; -- Sollte Fehler werfen
-- SELECT count(*) FROM storage.objects WHERE bucket_id = 'submissions'; -- Sollte 0 oder Fehler sein