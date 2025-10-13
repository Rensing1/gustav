-- Alternativer Ansatz für Storage Upload RLS (Direkter Check)

-- 1. Alte INSERT Policy löschen
DROP POLICY IF EXISTS "Allow teachers to upload to materials bucket" ON storage.objects;

-- 2. Neue INSERT Policy mit direktem Check auf profiles
CREATE POLICY "Allow teachers to upload (direct check)"
  ON storage.objects FOR INSERT
  WITH CHECK (
    (bucket_id = 'materials') AND
    (
      -- Prüfe direkt in der profiles Tabelle, ob der aktuelle Nutzer ein Lehrer ist
      SELECT role FROM public.profiles WHERE id = auth.uid()
    ) = 'teacher'::public.user_role -- Expliziter Cast zum ENUM Typ
  );

-- Optional: Alte UPDATE/DELETE Policies auch anpassen (falls sie auch Probleme machen)
DROP POLICY IF EXISTS "Allow teachers to update materials" ON storage.objects;
CREATE POLICY "Allow teachers to update materials (direct check)"
  ON storage.objects FOR UPDATE
  USING (
     (bucket_id = 'materials') AND
     (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'teacher'::public.user_role
  )
  WITH CHECK (
     (bucket_id = 'materials') AND
     (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'teacher'::public.user_role
  );

DROP POLICY IF EXISTS "Allow teachers to delete materials" ON storage.objects;
CREATE POLICY "Allow teachers to delete materials (direct check)"
  ON storage.objects FOR DELETE
  USING (
     (bucket_id = 'materials') AND
     (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'teacher'::public.user_role
  );