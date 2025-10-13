-- Migration: Füge RLS SELECT Policy für Schüler auf learning_unit hinzu

-- 1. Lösche evtl. alte, nicht mehr passende Schüler-SELECT-Policies auf learning_unit
DROP POLICY IF EXISTS "Allow students to view published units in enrolled courses" ON public.learning_unit;
DROP POLICY IF EXISTS "Students view units assigned to their courses" ON public.learning_unit; -- Neuer Name, falls schon versucht

-- 2. Erstelle die neue SELECT-Policy für Schüler
--    Erlaubt Schülern das Sehen von Lerneinheiten, die einem ihrer Kurse zugewiesen sind.
CREATE POLICY "Students view units assigned to their courses"
  ON public.learning_unit FOR SELECT -- Nur Lesezugriff
  USING (
    get_my_role() = 'student' AND -- Nur für Schüler
    EXISTS ( -- Prüfe, ob eine Zuweisung zu einem Kurs des Schülers existiert
      SELECT 1
      FROM public.course_learning_unit_assignment clua
      JOIN public.course_student cs ON clua.course_id = cs.course_id
      WHERE clua.unit_id = learning_unit.id -- Verknüpfung zur aktuellen Lerneinheit-Zeile
        AND cs.student_id = auth.uid()      -- Für den aktuellen Schüler
    )
  );

-- Hinweis: Die Policy für Lehrer ("Allow teachers full access to learning units") bleibt unverändert.