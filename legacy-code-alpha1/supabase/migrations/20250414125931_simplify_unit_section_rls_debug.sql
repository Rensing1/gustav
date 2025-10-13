-- DEBUGGING: Radikal vereinfachte RLS für unit_section

-- 1. Alle alten Policies für unit_section löschen (Namen könnten variieren)
DROP POLICY IF EXISTS "Allow teachers full access to sections in their units" ON public.unit_section;
DROP POLICY IF EXISTS "Allow students to view published sections in their courses" ON public.unit_section;
DROP POLICY IF EXISTS "Allow students to view published sections in their courses v2" ON public.unit_section;
DROP POLICY IF EXISTS "Allow teachers full access to sections in their units v2" ON public.unit_section;


-- 2. Neue, extrem einfache Policies erstellen

-- Lehrer: Erlaube ALLES (ohne komplexe Checks)
CREATE POLICY "DEBUG Teacher Full Access unit_section"
  ON public.unit_section FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');

-- Schüler: Erlaube SELECT für alle (Nur zum Testen der Rekursion!)
-- ACHTUNG: Das ist unsicher und nur zum Debuggen!
CREATE POLICY "DEBUG Student Select All unit_section"
  ON public.unit_section FOR SELECT
  USING (get_my_role() = 'student');