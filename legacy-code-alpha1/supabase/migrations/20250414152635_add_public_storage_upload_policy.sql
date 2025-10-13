-- Lösche alle vorherigen, komplizierteren Policies für storage.objects (zur Sicherheit)
DROP POLICY IF EXISTS "Allow teachers to upload based on owner role" ON storage.objects;
DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to update materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow owner (if teacher) or any teacher to delete materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete via func check" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to upload (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update materials (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete materials (direct check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow any authenticated user to upload to materials" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to update materials (func check)" ON storage.objects;
DROP POLICY IF EXISTS "Allow teachers to delete materials (func check)" ON storage.objects;
-- Füge hier ggf. weitere Policy-Namen hinzu, die wir ausprobiert haben.

-- Erstelle die einfache INSERT Policy für den öffentlichen Bucket
-- Erlaubt jedem (auch anonym, wenn Bucket public ist und anon Lesezugriff hat)
-- das Einfügen in den spezifischen Bucket.
CREATE POLICY "Allow public insert to materials bucket"
  ON storage.objects FOR INSERT
  WITH CHECK ( bucket_id = 'materials' );

-- Optional: Füge eine einfache SELECT Policy hinzu (gut für Klarheit)
-- Erlaubt jedem das Lesen aus dem Bucket (wird durch Bucket-Einstellung eh erlaubt)
CREATE POLICY "Allow public select from materials bucket"
  ON storage.objects FOR SELECT
  USING ( bucket_id = 'materials' );

-- WICHTIG: Keine UPDATE/DELETE Policies für 'public' oder 'authenticated' hier,
-- da wir nicht wollen, dass jeder einfach Dateien ändern/löschen kann.
-- Die Lehrer-UPDATE/DELETE-Policies (die wir vorher hatten und die die Rolle prüfen)
-- können wir später wieder hinzufügen, wenn wir sie brauchen und sicher sind, dass sie funktionieren.
-- Vorerst konzentrieren wir uns nur auf den Upload.