-- RLS Policies für Schema v2.1 (Abschnitte) anpassen/hinzufügen

-- 1. RLS für neue Tabellen aktivieren
ALTER TABLE public.unit_section ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_unit_section_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_learning_unit_assignment ENABLE ROW LEVEL SECURITY;

-- 2. Policies für unit_section
-- Lehrer: Vollzugriff auf Abschnitte von Einheiten, die sie erstellt haben (Verfeinerung!)
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

-- Schüler: Lesezugriff auf Abschnitte, die für ihren Kurs freigegeben sind
CREATE POLICY "Allow students to view published sections in their courses"
  ON public.unit_section FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1
      FROM public.course_unit_section_status cuss
      JOIN public.course_student cs ON cuss.course_id = cs.course_id
      WHERE cuss.section_id = unit_section.id
        AND cs.student_id = auth.uid()
        AND cuss.is_published = true
    )
  );

-- 3. Policies für course_unit_section_status
-- Lehrer: Können Status für Abschnitte in Einheiten ändern, die sie erstellt haben
CREATE POLICY "Allow teachers to manage section status in their units"
  ON public.course_unit_section_status FOR ALL
  USING ( -- Wer darf sehen/löschen?
    get_my_role() = 'teacher' AND
    EXISTS (
      SELECT 1
      FROM public.unit_section us
      JOIN public.learning_unit lu ON us.unit_id = lu.id
      WHERE us.id = course_unit_section_status.section_id
        AND lu.creator_id = auth.uid()
    )
  )
  WITH CHECK ( -- Wer darf einfügen/ändern?
    get_my_role() = 'teacher' AND
    EXISTS (
      SELECT 1
      FROM public.unit_section us
      JOIN public.learning_unit lu ON us.unit_id = lu.id
      WHERE us.id = course_unit_section_status.section_id
        AND lu.creator_id = auth.uid()
    )
  );
-- Schüler: Kein direkter Zugriff nötig, Sichtbarkeit wird über unit_section/task geprüft.

-- 4. Policies für course_learning_unit_assignment
-- Lehrer: Können Einheiten zu Kursen zuweisen (Prototyp: Alle Kurse)
CREATE POLICY "Allow teachers to assign units to courses"
  ON public.course_learning_unit_assignment FOR ALL
  USING (get_my_role() = 'teacher') -- Lehrer sehen alle Zuweisungen
  WITH CHECK (get_my_role() = 'teacher'); -- Lehrer können Zuweisungen erstellen/ändern

-- Schüler: Können Zuweisungen für ihre Kurse sehen (indirekt nützlich)
CREATE POLICY "Allow students to view assignments for their courses"
  ON public.course_learning_unit_assignment FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1
      FROM public.course_student cs
      WHERE cs.course_id = course_learning_unit_assignment.course_id
        AND cs.student_id = auth.uid()
    )
  );


-- 5. Policy für task (SELECT für Schüler) aktualisieren
-- Alte Policy löschen (die task.is_published verwendet haben könnte)
DROP POLICY IF EXISTS "Students view published tasks in published units in enrolled courses" ON public.task;
-- Ggf. auch den alten Namen löschen, falls die Policy anders hieß
DROP POLICY IF EXISTS "Allow students to view tasks of published units in enrolled courses" ON public.task;

-- 6. Policy für task (INSERT/UPDATE/DELETE für Lehrer) aktualisieren
-- Alte Policy löschen
DROP POLICY IF EXISTS "Allow teachers full access to tasks" ON public.task;

-- !!! NEU: JETZT die Spalte löschen, NACHDEM die Policies weg sind !!!
ALTER TABLE public.task
  DROP COLUMN IF EXISTS is_published CASCADE; -- CASCADE zur Sicherheit

-- !!! ENDE NEU !!!

-- Neue SELECT Policy erstellen (ohne is_published)
CREATE POLICY "Students view tasks in published sections in their courses"
  ON public.task FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS ( -- Prüft, ob der übergeordnete Abschnitt sichtbar ist
      SELECT 1
      FROM public.unit_section us
      WHERE us.id = task.section_id
    )
  );

-- Neue ALL Policy für Lehrer erstellen (ohne is_published)
CREATE POLICY "Allow teachers full access to tasks in their units"
  ON public.task FOR ALL
  USING ( -- Wer darf sehen/löschen/updaten? Lehrer, deren Einheit der Abschnitt gehört
    get_my_role() = 'teacher' AND
    EXISTS (
        SELECT 1
        FROM public.unit_section us
        JOIN public.learning_unit lu ON us.unit_id = lu.id
        WHERE us.id = task.section_id AND lu.creator_id = auth.uid()
    )
  )
  WITH CHECK ( -- Wer darf einfügen/updaten? Lehrer, deren Einheit der Abschnitt gehört
    get_my_role() = 'teacher' AND
    EXISTS (
        SELECT 1
        FROM public.unit_section us
        JOIN public.learning_unit lu ON us.unit_id = lu.id
        WHERE us.id = task.section_id AND lu.creator_id = auth.uid()
    )
  );

-- 7. Policy für submission (INSERT für Schüler) aktualisieren
-- Alte Policy löschen
DROP POLICY IF EXISTS "Allow students to insert their own submission once" ON public.submission;

-- Neue Policy erstellen, die Task-Sichtbarkeit prüft
CREATE POLICY "Allow students to insert submission for visible tasks once"
  ON public.submission FOR INSERT
  WITH CHECK (
    get_my_role() = 'student' AND
    student_id = auth.uid() AND
    EXISTS ( -- Check if student is allowed to view the task
      SELECT 1 FROM public.task t
      WHERE t.id = submission.task_id
      -- RLS on task table implicitly handles visibility check here
    )
  );

-- 8. Policies für submission (SELECT/UPDATE/DELETE für Lehrer) aktualisieren
-- Alte Policies löschen
DROP POLICY IF EXISTS "Allow teachers to view submissions in their units" ON public.submission;
DROP POLICY IF EXISTS "Allow teachers to update submissions in their units" ON public.submission;
DROP POLICY IF EXISTS "Allow teachers to delete submissions in their units" ON public.submission;

-- Neue Policies erstellen, die über Abschnitt/Einheit prüfen
CREATE POLICY "Teachers view submissions for tasks in their units"
  ON public.submission FOR SELECT
  USING (
    get_my_role() = 'teacher' AND
    EXISTS (
      SELECT 1 FROM public.task t
      JOIN public.unit_section us ON t.section_id = us.id
      JOIN public.learning_unit lu ON us.unit_id = lu.id
      WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
    )
  );

CREATE POLICY "Teachers update submissions for tasks in their units"
  ON public.submission FOR UPDATE
  USING (
    get_my_role() = 'teacher' AND
    EXISTS (
      SELECT 1 FROM public.task t
      JOIN public.unit_section us ON t.section_id = us.id
      JOIN public.learning_unit lu ON us.unit_id = lu.id
      WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
    )
  )
  WITH CHECK (get_my_role() = 'teacher'); -- Einfacher Check reicht hier

CREATE POLICY "Teachers delete submissions for tasks in their units"
  ON public.submission FOR DELETE
  USING (
    get_my_role() = 'teacher' AND
    EXISTS (
      SELECT 1 FROM public.task t
      JOIN public.unit_section us ON t.section_id = us.id
      JOIN public.learning_unit lu ON us.unit_id = lu.id
      WHERE t.id = submission.task_id AND lu.creator_id = auth.uid()
    )
  );