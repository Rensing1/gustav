-- RLS Policies für Schema v3 anpassen/hinzufügen

-- 1. RLS für neue Tabellen aktivieren
ALTER TABLE public.learning_material ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_learning_material ENABLE ROW LEVEL SECURITY;

-- 2. Policies für learning_material
-- Lehrer: Vollzugriff (Prototyp-Vereinfachung)
CREATE POLICY "Allow teachers full access to learning materials"
  ON public.learning_material FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');

-- Schüler: Lesezugriff auf Materialien, die zu sichtbaren Aufgaben gehören
CREATE POLICY "Allow students to view materials for visible tasks"
  ON public.learning_material FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1
      FROM public.task_learning_material tlm
      JOIN public.task t ON tlm.task_id = t.id -- JOIN zur Aufgabe
      -- Die Sichtbarkeit von 't' wird durch die RLS der 'task'-Tabelle geprüft.
      -- Wenn der Schüler die Aufgabe 't' sehen darf (SELECT-Policy auf task greift),
      -- dann darf er auch das verknüpfte Material sehen.
      WHERE tlm.material_id = learning_material.id
    )
  );

-- 3. Policies für task_learning_material
-- Lehrer: Vollzugriff (Prototyp-Vereinfachung)
CREATE POLICY "Allow teachers full access to task material links"
  ON public.task_learning_material FOR ALL
  USING (get_my_role() = 'teacher')
  WITH CHECK (get_my_role() = 'teacher');

-- Schüler: Lesezugriff auf Verknüpfungen, wenn die Aufgabe sichtbar ist
CREATE POLICY "Allow students to view links for visible tasks"
  ON public.task_learning_material FOR SELECT
  USING (
    get_my_role() = 'student' AND
    EXISTS (
      SELECT 1
      FROM public.task t
      -- Die Sichtbarkeit von 't' wird durch die RLS der 'task'-Tabelle geprüft.
      WHERE t.id = task_learning_material.task_id
    )
  );

-- 4. Policy für task (SELECT für Schüler) aktualisieren
-- Alte Policy löschen (Name muss exakt stimmen!)
DROP POLICY IF EXISTS "Allow students to view tasks of published units in enrolled courses" ON public.task;
-- Ggf. auch den neuen Namen löschen, falls schon mal angewendet
DROP POLICY IF EXISTS "Students view published tasks in published units in enrolled courses" ON public.task;

-- Neue Policy erstellen, die task.is_published prüft
CREATE POLICY "Students view published tasks in published units in enrolled courses"
  ON public.task FOR SELECT
  USING (
    get_my_role() = 'student' AND
    task.is_published = true AND -- <<< NEUE BEDINGUNG
    EXISTS ( -- Prüft, ob die übergeordnete Lerneinheit sichtbar ist
      SELECT 1
      FROM public.learning_unit lu
      -- Die Sichtbarkeit von 'lu' wird durch die RLS der 'learning_unit'-Tabelle geprüft,
      -- welche die Kurszugehörigkeit und Veröffentlichung der Einheit im Kurs checkt.
      WHERE lu.id = task.unit_id
    )
  );