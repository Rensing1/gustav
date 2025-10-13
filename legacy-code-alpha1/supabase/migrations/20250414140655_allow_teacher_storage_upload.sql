-- Erlaube Lehrern das Hochladen von Dateien in den 'materials' Bucket

-- Policy für INSERT auf storage.objects
-- Erlaubt einem authentifizierten Benutzer das Einfügen, wenn er die Rolle 'teacher' hat
-- und der Bucket 'materials' ist.
CREATE POLICY "Allow teachers to upload to materials bucket"
  ON storage.objects FOR INSERT
  -- Prüfe die Rolle des Benutzers über unsere Hilfsfunktion
  WITH CHECK ( (bucket_id = 'materials') AND (get_my_role() = 'teacher') );

-- Optional: Policy für SELECT (Lesen) - Für öffentlichen Bucket nicht zwingend,
-- aber gut für spätere Umstellung auf privaten Bucket.
-- Erlaubt jedem authentifizierten Nutzer das Lesen aus dem materials Bucket.
-- (Später könnte man dies auf Schüler beschränken, die Zugriff auf den Abschnitt haben)
-- CREATE POLICY "Allow authenticated read access to materials"
--  ON storage.objects FOR SELECT
--  USING ( bucket_id = 'materials' );

-- Optional: Policy für UPDATE (falls Lehrer Dateien ersetzen sollen)
CREATE POLICY "Allow teachers to update materials"
  ON storage.objects FOR UPDATE
  USING ( (bucket_id = 'materials') AND (get_my_role() = 'teacher') ) -- Wer darf die Zeile auswählen?
  WITH CHECK ( (bucket_id = 'materials') AND (get_my_role() = 'teacher') ); -- Welche neuen Daten sind ok?

-- Optional: Policy für DELETE (falls Lehrer Dateien löschen sollen)
CREATE POLICY "Allow teachers to delete materials"
  ON storage.objects FOR DELETE
  USING ( (bucket_id = 'materials') AND (get_my_role() = 'teacher') );