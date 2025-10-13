-- Fix für RLS Rekursion bei unit_section

-- 1. Alte Schüler-SELECT-Policy löschen
DROP POLICY IF EXISTS "Allow students to view published sections in their courses" ON public.unit_section;

-- 2. Neue Schüler-SELECT-Policy erstellen
--    Prüft, ob der Schüler in einem Kurs ist, für den dieser Abschnitt veröffentlicht ist.
CREATE POLICY "Allow students to view published sections in their courses v2"
  ON public.unit_section FOR SELECT
  USING (
    get_my_role() = 'student' AND
    id IN ( -- Wähle nur Abschnitt-IDs aus, die die Kriterien erfüllen
      SELECT cuss.section_id
      FROM public.course_unit_section_status cuss
      JOIN public.course_student cs ON cuss.course_id = cs.course_id
      WHERE cs.student_id = auth.uid()
        AND cuss.is_published = true
    )
  );

-- 3. Optional: Lehrer-Policy zur Sicherheit auch neu erstellen (obwohl wahrscheinlich nicht die Ursache)
--    Die Logik bleibt gleich, aber manchmal hilft das Neuanlegen.
DROP POLICY IF EXISTS "Allow teachers full access to sections in their units" ON public.unit_section;

CREATE POLICY "Allow teachers full access to sections in their units v2"
  ON public.unit_section FOR ALL
  USING (
    get_my_role() = 'teacher' AND
    EXISTS (SELECT 1 FROM public.learning_unit lu WHERE lu.id = unit_section.unit_id AND lu.creator_id = auth.uid())
  )
  WITH CHECK (
    get_my_role() = 'teacher' AND
    EXISTS (SELECT 1 FROM public.learning_unit lu WHERE lu.id = unit_section.unit_id AND lu.creator_id = auth.uid())
  );