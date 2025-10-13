-- Migration: Fix submissions storage upload policy
-- Datum: 2025-08-27
-- Zweck: Repariert defekte INSERT Policy fuer submissions bucket

-- Entferne die defekte Policy (mit leerem qual)
DROP POLICY IF EXISTS "Users can upload own submission files" ON storage.objects;

-- Erstelle korrekte INSERT Policy fuer submissions
CREATE POLICY "Users can upload own submission files"
ON storage.objects FOR INSERT 
TO authenticated
WITH CHECK (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Zusaetzliche Policy: Benutzer koennen ihre eigenen Dateien aktualisieren
CREATE POLICY "Users can update own submission files"
ON storage.objects FOR UPDATE
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);