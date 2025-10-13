-- Migration: Passe RLS für SELECT auf profiles an, damit Lehrer Nutzer sehen können

-- 1. Alte SELECT-Policy für profiles löschen
--    (Der Name muss exakt mit dem aus deiner vorherigen Migration übereinstimmen!)
DROP POLICY IF EXISTS "Allow individual user access to own profile" ON public.profiles;
-- Sicherheitshalber auch den neuen Namen löschen, falls schon mal versucht
DROP POLICY IF EXISTS "Allow users to view profiles based on role" ON public.profiles;


-- 2. Neue SELECT-Policy für profiles erstellen
CREATE POLICY "Allow users to view profiles based on role"
  ON public.profiles FOR SELECT
  USING (
    -- Bedingung 1: Jeder Nutzer kann immer sein eigenes Profil sehen.
    (auth.uid() = id)
    OR
    -- Bedingung 2: Wenn der anfragende Nutzer die Rolle 'teacher' hat, darf er ALLE Profile sehen.
    -- Die Funktion get_my_role() gibt die Rolle des aktuell authentifizierten Nutzers zurück.
    (public.get_my_role() = 'teacher') -- Stelle sicher, dass das Schema public explizit ist
  );

-- Hinweis: Die UPDATE-Policy "Allow individual user update to own profile" kann unverändert bleiben,
-- da Nutzer weiterhin nur ihr eigenes Profil bearbeiten können sollen.