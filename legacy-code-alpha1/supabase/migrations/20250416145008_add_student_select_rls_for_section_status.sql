-- Migration: Füge RLS SELECT Policy für Schüler auf course_unit_section_status hinzu

-- 1. Lösche evtl. alte, nicht mehr passende Schüler-SELECT-Policies auf dieser Tabelle
DROP POLICY IF EXISTS "Students can view their section statuses" ON public.course_unit_section_status;

-- 2. Erstelle die neue SELECT-Policy für Schüler
--    Erlaubt Schülern das Lesen von Status-Einträgen, die zu einem ihrer Kurse gehören.
CREATE POLICY "Students can view their section statuses"
  ON public.course_unit_section_status FOR SELECT -- Nur Lesezugriff
  USING (
    get_my_role() = 'student' AND -- Nur für Schüler
    EXISTS ( -- Prüfe, ob der Status-Eintrag zu einem Kurs gehört, in dem der Schüler ist
      SELECT 1
      FROM public.course_student cs
      WHERE cs.course_id = course_unit_section_status.course_id -- Verknüpfung zum aktuellen Status-Eintrag
        AND cs.student_id = auth.uid()                          -- Für den aktuellen Schüler
    )
  );

-- Hinweis: Die Policy für Lehrer ("Allow teachers to manage section status in their units") bleibt unverändert.