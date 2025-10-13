-- Migration: Füge E-Mail zu Profilen hinzu und korrigiere Kurs-Links

-- 1. Füge die E-Mail-Spalte zur 'profiles'-Tabelle hinzu
ALTER TABLE public.profiles
  ADD COLUMN email TEXT; -- E-Mail kann sich ändern, daher TEXT

-- Index für schnellere E-Mail-Suche (optional, aber gut)
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);


-- 2. Aktualisiere die Trigger-Funktion 'handle_new_user', um die E-Mail zu kopieren
--    WICHTIG: Diese Funktion läuft mit SECURITY DEFINER Rechten!
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER -- Läuft als 'postgres' oder Superuser
SET search_path = public -- Sicherstellen, dass public Schema verwendet wird
AS $$
BEGIN
  -- Füge eine neue Zeile in public.profiles ein
  -- Kopiere die ID und die E-Mail aus dem neuen auth.users Eintrag
  INSERT INTO public.profiles (id, role, email, full_name) -- Füge email und ggf. full_name hinzu
  VALUES (
    NEW.id,
    'student', -- Standardrolle 'student'
    NEW.email, -- Kopiere die E-Mail vom Auth-User
    NEW.raw_user_meta_data->>'full_name' -- Versuche, den Namen aus Metadaten zu holen (optional)
  );
  RETURN NEW;
END;
$$;
-- Hinweis: Der Trigger 'on_auth_user_created' muss nicht geändert werden, er ruft weiterhin handle_new_user auf.


-- 3. Ändere die Foreign Keys in 'course_student' und 'course_teacher'
--    Sie sollen jetzt direkt auf 'profiles(id)' statt 'auth.users(id)' zeigen.

-- Erst die alten Constraints löschen (Namen könnten variieren, prüfe ggf. im Supabase Studio)
-- Typische Namen sind <tabelle>_<spalte>_fkey
ALTER TABLE public.course_student
  DROP CONSTRAINT IF EXISTS course_student_student_id_fkey; -- Annahme des Namens

ALTER TABLE public.course_teacher
  DROP CONSTRAINT IF EXISTS course_teacher_teacher_id_fkey; -- Annahme des Namens

-- Dann die Spalten so ändern, dass sie auf 'profiles' verweisen
-- (Das Ändern des FK erfordert oft diesen Drop/Add-Ansatz)
ALTER TABLE public.course_student
  ADD CONSTRAINT course_student_student_id_fkey FOREIGN KEY (student_id)
  REFERENCES public.profiles(id) ON DELETE CASCADE; -- NEU: Referenziert profiles

ALTER TABLE public.course_teacher
  ADD CONSTRAINT course_teacher_teacher_id_fkey FOREIGN KEY (teacher_id)
  REFERENCES public.profiles(id) ON DELETE CASCADE; -- NEU: Referenziert profiles


-- 4. Optional: Aktualisiere bestehende Einträge in 'profiles', um die E-Mail zu füllen
--    (Nur nötig, wenn schon User existieren, die vor dieser Migration erstellt wurden)
-- UPDATE public.profiles p
-- SET email = (SELECT email FROM auth.users u WHERE u.id = p.id)
-- WHERE p.email IS NULL;