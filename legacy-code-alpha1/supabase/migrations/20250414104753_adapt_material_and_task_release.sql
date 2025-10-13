-- Migration von Schema v2 zu v3: Materialien auslagern, Aufgaben-Freigabe hinzufügen

-- 1. Neuen ENUM Typ für Materialarten erstellen
CREATE TYPE public.material_type AS ENUM (
  'text',
  'markdown',
  'video_url',
  'image_url',
  'pdf_url',
  'storage_object' -- Für Dateien in Supabase Storage
);
-- Berechtigung für den Typ gewähren
GRANT usage ON TYPE public.material_type TO anon, authenticated;


-- 2. Neue Tabelle für Lernmaterialien erstellen
CREATE TABLE public.learning_material (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type material_type NOT NULL,
    title TEXT,
    content JSONB NOT NULL, -- Enthält Text, URL, Storage-Pfad-Metadaten etc.
    creator_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Indizes
CREATE INDEX idx_learning_material_creator_id ON public.learning_material(creator_id);
CREATE INDEX idx_learning_material_type ON public.learning_material(type);
-- Berechtigungen (Basis, RLS folgt)
GRANT select ON public.learning_material TO anon, authenticated;
-- Trigger für updated_at (falls nicht global aktiv)
-- CREATE TRIGGER on_learning_material_update BEFORE UPDATE ON public.learning_material FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();


-- 3. Neue Verknüpfungstabelle Task <-> Material erstellen
CREATE TABLE public.task_learning_material (
    task_id uuid NOT NULL REFERENCES public.task(id) ON DELETE CASCADE,
    material_id uuid NOT NULL REFERENCES public.learning_material(id) ON DELETE CASCADE,
    order_in_task INTEGER,
    PRIMARY KEY (task_id, material_id)
);
-- Indizes
CREATE INDEX idx_task_learning_material_material_id ON public.task_learning_material(material_id);
-- Berechtigungen (Basis, RLS folgt)
GRANT select ON public.task_learning_material TO anon, authenticated;


-- 4. Tabelle 'task' anpassen
-- Alte Spalte entfernen (Vorsicht bei bestehenden Daten - hier OK wegen db reset)
ALTER TABLE public.task
  DROP COLUMN IF EXISTS learning_material;

-- Neue Spalte für individuelle Freigabe hinzufügen
ALTER TABLE public.task
  ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT false;

-- Index für die neue Spalte
CREATE INDEX idx_task_is_published ON public.task(is_published);