-- Erstelle eine Hilfsfunktion, um die Rolle eines Nutzers sicher zu prüfen
-- Läuft als Ersteller (postgres) und kann daher profiles lesen, ignoriert aber RLS nicht generell.
CREATE OR REPLACE FUNCTION public.is_user_role(user_id_to_check uuid, role_to_check public.user_role)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER -- Läuft als 'postgres'
STABLE
-- WICHTIG: Setze search_path, um sicherzustellen, dass Typen und Tabellen gefunden werden
SET search_path = public
AS $$
DECLARE
  real_role public.user_role;
BEGIN
  SELECT role INTO real_role FROM public.profiles WHERE id = user_id_to_check;
  RETURN real_role = role_to_check;
EXCEPTION
  -- Falls Nutzer kein Profil hat (sollte nicht passieren) oder anderer Fehler
  WHEN OTHERS THEN
    RETURN FALSE;
END;
$$;

-- Erlaube authentifizierten Nutzern (wie dem Storage Service, der mit JWT agiert) die Funktion aufzurufen
GRANT EXECUTE ON FUNCTION public.is_user_role(uuid, public.user_role) TO authenticated;
-- Optional auch für service_role, falls nötig
-- GRANT EXECUTE ON FUNCTION public.is_user_role(uuid, public.user_role) TO service_role;


-- Passe die Storage RLS Policies an, um die neue Funktion zu nutzen

-- Alte Policies löschen (Namen könnten von vorherigen Versuchen abweichen)
DROP POLICY IF EXISTS "Allow teachers to upload to materials bucket" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update materials (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete materials (direct check)" ON storage.objects;

-- Neue INSERT Policy mit Funktionsaufruf
CREATE POLICY "Allow teachers to upload via func check"
  ON storage.objects FOR INSERT
  WITH CHECK (
    (bucket_id = 'materials') AND
    -- Rufe die Funktion auf, um zu prüfen, ob der aktuelle Nutzer (auth.uid()) ein Lehrer ist
    public.is_user_role(auth.uid(), 'teacher')
  );

-- Neue UPDATE Policy mit Funktionsaufruf
CREATE POLICY "Allow teachers to update via func check"
  ON storage.objects FOR UPDATE
  USING ( -- USING prüft, wer die Zeile überhaupt sehen/auswählen darf für das Update
     (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher')
  )
  WITH CHECK ( -- WITH CHECK prüft die neuen/geänderten Daten
     (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher')
  );

-- Neue DELETE Policy mit Funktionsaufruf
CREATE POLICY "Allow teachers to delete via func check"
  ON storage.objects FOR DELETE
  USING (
     (bucket_id = 'materials') AND public.is_user_role(auth.uid(), 'teacher')
  );