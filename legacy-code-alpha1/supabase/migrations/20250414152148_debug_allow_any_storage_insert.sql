-- DEBUGGING: Erlaube JEDEN INSERT in den materials Bucket (UNSICHER!)

-- 1. Alle alten INSERT Policies löschen
DROP POLICY IF EXISTS "Allow teachers to upload based on owner role" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow any authenticated user to upload to materials" ON storage.objects;

-- 2. Neue Policy, die IMMER erlaubt (nur für den materials Bucket)
CREATE POLICY "TEMP DEBUG Allow any insert into materials bucket"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'materials'); -- Prüft NUR den Bucket-Namen

-- Behalte die restriktiveren UPDATE/DELETE Policies vorerst bei
-- (oder kommentiere sie auch aus, wenn du nur den INSERT testen willst)