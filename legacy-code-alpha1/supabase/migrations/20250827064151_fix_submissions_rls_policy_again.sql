-- Migration: Fix submissions RLS policy wieder
-- Datum: 2025-08-27
-- Zweck: Repariert RLS Policy fuer submissions bucket erneut

-- Entferne alle existierenden submissions policies
DROP POLICY IF EXISTS "Users can upload own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can view own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can update own submission files" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete own submission files" ON storage.objects;

-- Erstelle neue, korrekte Policies fuer submissions bucket
-- INSERT Policy (wichtigste fuer File Upload)
CREATE POLICY "submissions_insert_policy"
ON storage.objects FOR INSERT 
TO authenticated
WITH CHECK (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- SELECT Policy (zum Anzeigen eigener Dateien)
CREATE POLICY "submissions_select_policy"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- UPDATE Policy (zum Aktualisieren eigener Dateien)  
CREATE POLICY "submissions_update_policy"
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

-- DELETE Policy (zum Loeschen eigener Dateien)
CREATE POLICY "submissions_delete_policy"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Zusaetzliche Policy: Lehrer koennen Submission Files ihrer Schueler einsehen
CREATE POLICY "submissions_teacher_view_policy"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'submissions' 
    AND EXISTS (
        SELECT 1 FROM submission s
        WHERE s.file_path = objects.name
          AND s.student_id::text = (storage.foldername(objects.name))[1]
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