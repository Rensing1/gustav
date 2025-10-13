-- Vereinfache Storage RLS für Upload: Erlaube jedem authentifizierten Nutzer

-- 1. Alte Policies löschen (Namen könnten variieren)
DROP POLICY IF EXISTS "Allow teachers to upload based on owner role" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload (direct check)" ON storage.objects;
-- Lösche auch die temporäre Debug-Policy, falls vorhanden
DROP POLICY IF EXISTS "TEMP Allow any authenticated user to upload to materials" ON storage.objects;

-- 2. Neue, einfache INSERT Policy: Erlaubt jedem authentifizierten Nutzer in den Bucket zu schreiben
CREATE POLICY "Allow any authenticated user to upload to materials"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'materials' AND
    auth.role() = 'authenticated' -- Prüft nur, ob der Nutzer eingeloggt ist
  );

-- 3. UPDATE/DELETE Policies (optional, vorerst beibehalten mit Lehrer-Check via Funktion)
--    Diese werden erst relevant, wenn ein Lehrer versucht, eine Datei zu löschen/ersetzen.
--    Wir können sie vorerst so lassen oder auch vereinfachen, wenn nötig.
DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to update materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update (direct check)" ON storage.objects;
CREATE POLICY "Allow teachers to update materials (func check)"
  ON storage.objects FOR UPDATE
  USING ( (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher') )
  WITH CHECK ( (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher') );

DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to delete materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete (direct check)" ON storage.objects;
CREATE POLICY "Allow teachers to delete materials (func check)"
  ON storage.objects FOR DELETE
  USING ( (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher') );