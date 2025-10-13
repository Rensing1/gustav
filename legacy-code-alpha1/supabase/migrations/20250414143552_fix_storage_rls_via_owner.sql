-- Passe Storage RLS Policies an, um die 'owner'-Spalte zu nutzen

-- 1. Alte Policies löschen (Namen könnten variieren)
DROP POLICY IF EXISTS "Allow teachers to upload via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete (direct check)" ON storage.objects;
-- Lösche auch die temporäre Debug-Policy, falls vorhanden
DROP POLICY IF EXISTS "TEMP Allow any authenticated user to upload to materials" ON storage.objects;


-- 2. Neue INSERT Policy: Prüft die Rolle des designierten 'owner'
--    Wir gehen davon aus, dass die Storage API 'owner' korrekt mit der ID des
--    hochladenden Nutzers (aus dem JWT) befüllt.
CREATE POLICY "Allow teachers to upload based on owner role"
  ON storage.objects FOR INSERT
  WITH CHECK (
    (bucket_id = 'materials') AND
    -- Rufe die Hilfsfunktion auf, um die Rolle des 'owner' zu prüfen
    public.is_user_role(owner, 'teacher') -- Prüfe die Rolle der 'owner'-Spalte!
  );

-- 3. Neue UPDATE Policy: Erlaubt dem Owner (wenn Lehrer) oder jedem Lehrer das Update
CREATE POLICY "Allow owner (if teacher) or any teacher to update materials"
  ON storage.objects FOR UPDATE
  USING ( -- Wer darf die Zeile auswählen? Der Owner oder jeder Lehrer.
     (bucket_id = 'materials') AND
     ( (owner = auth.uid() AND public.is_user_role(owner, 'teacher')) OR public.is_user_role(auth.uid(), 'teacher') )
  )
  WITH CHECK ( -- Wer darf ändern? Nur der Owner (wenn Lehrer) oder ein anderer Lehrer.
     (bucket_id = 'materials') AND
     ( (owner = auth.uid() AND public.is_user_role(owner, 'teacher')) OR public.is_user_role(auth.uid(), 'teacher') )
  );
  -- Anmerkung: Diese Update-Policy ist relativ offen für Lehrer. Man könnte sie einschränken,
  -- sodass nur der Owner updaten darf, wenn das gewünscht ist.

-- 4. Neue DELETE Policy: Erlaubt dem Owner (wenn Lehrer) oder jedem Lehrer das Löschen
CREATE POLICY "Allow owner (if teacher) or any teacher to delete materials"
  ON storage.objects FOR DELETE
  USING (
     (bucket_id = 'materials') AND
     ( (owner = auth.uid() AND public.is_user_role(owner, 'teacher')) OR public.is_user_role(auth.uid(), 'teacher') )
  );

-- 5. Stelle sicher, dass die Hilfsfunktion existiert (aus vorheriger Migration)
--    (Kein Code hier nötig, nur zur Erinnerung)