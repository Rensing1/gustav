-- Migration: Create submissions storage bucket for file uploads
-- Datum: 2025-08-27
-- Zweck: Storage Bucket und Policies fuer File-Upload MVP

-- Erstelle submissions bucket falls nicht vorhanden
INSERT INTO storage.buckets (id, name, public)
VALUES ('submissions', 'submissions', false)
ON CONFLICT (id) DO NOTHING;

-- RLS Policy: Benutzer koennen nur ihre eigenen Dateien hochladen
-- Pfad-Format: submissions/{user_id}/{task_id}/filename
CREATE POLICY "Users can upload own submission files"
ON storage.objects FOR INSERT 
TO authenticated
WITH CHECK (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- RLS Policy: Benutzer koennen nur ihre eigenen Dateien lesen
CREATE POLICY "Users can view own submission files"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- RLS Policy: Benutzer koennen nur ihre eigenen Dateien loeschen  
CREATE POLICY "Users can delete own submission files"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- RLS Policy: Lehrer koennen Dateien ihrer Schueler sehen
-- (fuer spaetere Features wie Feedback auf Dateien)
CREATE POLICY "Teachers can view student submission files"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND EXISTS (
        SELECT 1 FROM submission s
        WHERE s.file_path = name
        AND s.student_id::text = (storage.foldername(name))[1]
        AND EXISTS (
            SELECT 1 FROM task t
            JOIN unit_section us ON t.section_id = us.id
            JOIN learning_unit lu ON us.unit_id = lu.id
            JOIN course_learning_unit_assignment cua ON lu.id = cua.unit_id
            JOIN course c ON cua.course_id = c.id  
            WHERE t.id = s.task_id
            AND c.creator_id = auth.uid()
        )
    )
);

-- RLS ist bereits auf storage.objects aktiviert