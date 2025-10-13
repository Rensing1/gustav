-- Migration: Setze RLS-Policy für 'course' auf Standardformat zurück

-- 1. Lösche die bestehende Policy (verwende den exakten Namen!)
DROP POLICY IF EXISTS "Allow teachers full access to courses" ON public.course;

-- 2. Erstelle die Policy neu mit Standard-Syntax
--    Diese Policy gilt für ALLE Operationen (SELECT, INSERT, UPDATE, DELETE)
CREATE POLICY "Allow teachers full access to courses"
  ON public.course -- Die Tabelle
  FOR ALL          -- Für alle Operationen
  USING (public.get_my_role() = 'teacher') -- Bedingung für SELECT / Ziel von UPDATE/DELETE
  WITH CHECK (public.get_my_role() = 'teacher'); -- Bedingung für INSERT / Daten von UPDATE

-- Hinweise:
-- - 'public.get_my_role()' stellt sicher, dass die Funktion im richtigen Schema gesucht wird.
-- - Der explizite Cast zu '::user_role' ist optional, wenn der Rückgabetyp der Funktion stimmt, schadet aber nicht.
-- - Es wird keine 'TO ...' Klausel benötigt.