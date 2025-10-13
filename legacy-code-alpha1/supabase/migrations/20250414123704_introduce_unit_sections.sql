-- Migration zu Schema v2.1: Einführung von Abschnitten (unit_section)

-- 1. Redundante Tabelle für Kurs-Einheit-Veröffentlichung löschen
DROP TABLE IF EXISTS public.course_learning_unit CASCADE;

-- 2. Spalte 'materials' aus 'learning_unit' entfernen
ALTER TABLE public.learning_unit
  DROP COLUMN IF EXISTS materials;

-- 3. Spalte 'is_published' aus 'task' entfernen
--ALTER TABLE public.task
--  DROP COLUMN IF EXISTS is_published;

-- 4. Neue Tabelle 'unit_section' erstellen
CREATE TABLE public.unit_section (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id uuid NOT NULL REFERENCES public.learning_unit(id) ON DELETE CASCADE,
    title TEXT,
    order_in_unit INTEGER NOT NULL DEFAULT 0,
    materials JSONB, -- Materialien für diesen Abschnitt
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Indizes
CREATE INDEX idx_unit_section_unit_id ON public.unit_section(unit_id);
CREATE INDEX idx_unit_section_order ON public.unit_section(unit_id, order_in_unit);
-- Berechtigungen (Basis, RLS folgt)
GRANT select, insert, update, delete ON public.unit_section TO authenticated;
-- Trigger für updated_at (falls nicht global aktiv)
-- CREATE TRIGGER on_unit_section_update BEFORE UPDATE ON public.unit_section FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();


-- 5. Tabelle 'task' anpassen: section_id hinzufügen, unit_id und order_in_unit entfernen
-- Erst Spalte hinzufügen
ALTER TABLE public.task
  ADD COLUMN section_id uuid REFERENCES public.unit_section(id) ON DELETE CASCADE;
-- Index für die neue Spalte
CREATE INDEX idx_task_section_id ON public.task(section_id);

-- Dann alte Spalten entfernen (geht nur, wenn keine FKs mehr darauf zeigen, was hier der Fall sein sollte)
ALTER TABLE public.task
  DROP COLUMN IF EXISTS unit_id CASCADE; -- CASCADE, falls doch noch was dranhängt
ALTER TABLE public.task
  DROP COLUMN IF EXISTS order_in_unit;

-- Neue Spalte für Reihenfolge innerhalb der Sektion hinzufügen
ALTER TABLE public.task
  ADD COLUMN order_in_section INTEGER;
CREATE INDEX idx_task_order_in_section ON public.task(section_id, order_in_section);


-- 6. Neue Tabelle 'course_unit_section_status' für Freigabe pro Kurs/Abschnitt
CREATE TABLE public.course_unit_section_status (
    course_id uuid NOT NULL REFERENCES public.course(id) ON DELETE CASCADE,
    section_id uuid NOT NULL REFERENCES public.unit_section(id) ON DELETE CASCADE,
    is_published BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMPTZ,
    PRIMARY KEY (course_id, section_id)
);
-- Indizes
CREATE INDEX idx_course_unit_section_status_section_id ON public.course_unit_section_status(section_id);
CREATE INDEX idx_course_unit_section_status_published ON public.course_unit_section_status(is_published);
-- Berechtigungen (Basis, RLS folgt)
GRANT select, insert, update, delete ON public.course_unit_section_status TO authenticated;


-- 7. Neue Tabelle 'course_learning_unit_assignment' für M:N Zuweisung Einheit <-> Kurs
CREATE TABLE public.course_learning_unit_assignment (
    course_id uuid NOT NULL REFERENCES public.course(id) ON DELETE CASCADE,
    unit_id uuid NOT NULL REFERENCES public.learning_unit(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, unit_id)
);
-- Indizes
CREATE INDEX idx_course_learning_unit_assignment_unit_id ON public.course_learning_unit_assignment(unit_id);
-- Berechtigungen (Basis, RLS folgt)
GRANT select, insert, update, delete ON public.course_learning_unit_assignment TO authenticated;