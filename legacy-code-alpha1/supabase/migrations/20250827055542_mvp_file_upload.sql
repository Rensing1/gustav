-- Migration: MVP File Upload Support
-- Datum: 2025-08-27
-- Zweck: Minimale Erweiterung der submission Tabelle fuer File-Upload MVP

-- Erweitere submission Tabelle um File-Upload Spalten
ALTER TABLE submission 
ADD COLUMN IF NOT EXISTS submission_type TEXT DEFAULT 'text' CHECK (submission_type IN ('text', 'file_upload')),
ADD COLUMN IF NOT EXISTS file_path TEXT,
ADD COLUMN IF NOT EXISTS original_filename TEXT,
ADD COLUMN IF NOT EXISTS extracted_text TEXT,
ADD COLUMN IF NOT EXISTS processing_stage TEXT DEFAULT 'pending' CHECK (processing_stage IN ('pending', 'processing', 'completed', 'failed'));

-- Index fuer Worker-Polling Performance
CREATE INDEX IF NOT EXISTS idx_submission_processing 
ON submission(processing_stage) 
WHERE processing_stage = 'pending';

-- Index fuer Cleanup-Operationen
CREATE INDEX IF NOT EXISTS idx_submission_type_created 
ON submission(submission_type, created_at);

-- Kommentar fuer Dokumentation
COMMENT ON COLUMN submission.submission_type IS 'Art der Einreichung: text oder file_upload';
COMMENT ON COLUMN submission.file_path IS 'Pfad zur Datei in Supabase Storage';
COMMENT ON COLUMN submission.original_filename IS 'Urspruenglicher Dateiname vom Upload';
COMMENT ON COLUMN submission.extracted_text IS 'Extrahierter Text aus Vision-Processing';
COMMENT ON COLUMN submission.processing_stage IS 'Status fuer File-Processing Pipeline';