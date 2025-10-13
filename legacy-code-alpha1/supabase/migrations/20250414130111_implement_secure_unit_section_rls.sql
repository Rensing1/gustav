-- Sichere RLS Policies für unit_section implementieren

-- 1. Debug-Policies löschen
DROP POLICY IF EXISTS "DEBUG Teacher Full Access unit_section" ON public.unit_section;
DROP POLICY IF EXISTS "DEBUG Student Select All unit_section" ON public.unit_section;

-- 2. Sichere Lehrer-Policy wiederherstellen (wie ursprünglich geplant)
CREATE POLICY "Allow teachers full access to sections in their units"
  ON public.unit_section FOR ALL
  USING (
    get_my_role() = 'teacher' AND
    EXISTS (SELECT 1 FROM public.learning_unit lu WHERE lu.id = unit_section.unit_id AND lu.creator_id = auth.uid())
  )
  WITH CHECK (
    get_my_role() = 'teacher' AND
    EXISTS (SELECT 1 FROM public.learning_unit lu WHERE lu.id = unit_section.unit_id AND lu.creator_id = auth.uid())
  );

-- 3. Hilfsfunktion für Schüler-Sichtbarkeit erstellen
CREATE OR REPLACE FUNCTION public.can_student_view_section(section_id_to_check uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER -- Wichtig, um auf alle nötigen Tabellen zugreifen zu können
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.course_unit_section_status cuss
    JOIN public.course_student cs ON cuss.course_id = cs.course_id
    WHERE cs.student_id = auth.uid() -- Ist der aktuelle Nutzer in einem Kurs...
      AND cuss.section_id = section_id_to_check -- ...der diesen Abschnitt enthält...
      AND cuss.is_published = true -- ...und ist dieser Abschnitt für den Kurs veröffentlicht?
  );
$$;
-- Berechtigung für die Funktion
GRANT EXECUTE ON FUNCTION public.can_student_view_section(uuid) TO authenticated;


-- 4. Sichere Schüler-SELECT-Policy erstellen, die die Hilfsfunktion nutzt
CREATE POLICY "Allow students to view published sections via helper"
  ON public.unit_section FOR SELECT
  USING (
    get_my_role() = 'student' AND
    public.can_student_view_section(id) -- Rufe die Hilfsfunktion für die aktuelle Zeilen-ID auf
  );