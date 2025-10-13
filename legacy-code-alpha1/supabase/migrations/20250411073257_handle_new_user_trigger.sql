-- Erstellt einen Eintrag in public.profiles für neue Benutzer in auth.users
-- Läuft mit den Rechten des Erstellers (SECURITY DEFINER), normalerweise 'postgres'
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER -- WICHTIG!
-- Setze den search_path, um sicherzustellen, dass die Funktion Tabellen im public Schema findet
SET search_path = public
AS $$
BEGIN
  -- Füge eine neue Zeile in public.profiles ein
  -- NEW bezieht sich auf die Zeile, die in auth.users eingefügt wurde
  INSERT INTO public.profiles (id, role)
  VALUES (NEW.id, 'student'); -- Standardrolle 'student'
  RETURN NEW;
END;
$$;

-- Trigger, der die Funktion nach jedem INSERT in auth.users aufruft
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Berechtigungen für die Funktion (normalerweise nicht nötig für SECURITY DEFINER, aber schadet nicht)
-- GRANT EXECUTE ON FUNCTION public.handle_new_user() TO postgres; -- Der Trigger läuft als 'postgres'