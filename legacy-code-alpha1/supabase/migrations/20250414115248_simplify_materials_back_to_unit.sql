-- Migration zurück zu Schema v2 (modifiziert): Materialien in Lerneinheit

-- 1. Verknüpfungstabelle löschen (CASCADE löst abhängige FKs auf)
DROP TABLE IF EXISTS public.task_learning_material CASCADE;

-- 2. Materialtabelle löschen (CASCADE löst abhängige FKs auf, inkl. RLS Policies)
DROP TABLE IF EXISTS public.learning_material CASCADE;

-- 3. ENUM Typ für Material löschen
DROP TYPE IF EXISTS public.material_type;

-- 4. Spalte 'learning_materials' (JSONB) zur 'learning_unit' Tabelle hinzufügen
ALTER TABLE public.learning_unit
  ADD COLUMN IF NOT EXISTS materials JSONB;

-- 5. RLS Policies für die gelöschten Tabellen entfernen <-- DIESEN BLOCK ENTFERNEN/AUSKOMMENTIEREN
-- DROP POLICY IF EXISTS "Allow teachers full access to learning materials" ON public.learning_material;
-- DROP POLICY IF EXISTS "Allow students to view materials for visible tasks" ON public.learning_material;
-- DROP POLICY IF EXISTS "Allow teachers full access to task material links" ON public.task_learning_material;
-- DROP POLICY IF EXISTS "Allow students to view links for visible tasks" ON public.task_learning_material;

-- 6. Sicherstellen, dass 'task.is_published' existiert (Keine Änderung nötig)
-- ALTER TABLE public.task ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT false;
-- CREATE INDEX IF NOT EXISTS idx_task_is_published ON public.task(is_published);

-- 7. RLS Policy für Task-SELECT (Schüler) ist bereits korrekt. (Keine Änderung nötig)