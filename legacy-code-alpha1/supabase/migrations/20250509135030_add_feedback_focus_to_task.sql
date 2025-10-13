-- Migration: Ersetze 'criteria' durch 'feedback_focus' in der Task-Tabelle

-- Optional: Erst alte Spalte löschen, WENN sie leer ist oder die Daten nicht migriert werden müssen
-- ALTER TABLE public.task DROP COLUMN IF EXISTS criteria;

-- Füge die neue Spalte 'feedback_focus' vom Typ TEXT hinzu.
-- Sie kann NULL sein, falls kein spezifischer Fokus angegeben wird.
ALTER TABLE public.task
  ADD COLUMN feedback_focus TEXT;

-- Optional: Kommentar hinzufügen
COMMENT ON COLUMN public.task.feedback_focus IS 'Vom Lehrer definierter Fokus für das KI-Feedback (z.B. spezifische Aspekte, die im Feedback behandelt werden sollen).';

-- Wenn die alte Spalte 'criteria' existiert hat und umbenannt werden soll:
-- (Nur ausführen, wenn 'criteria' existiert und die Daten relevant sind)
-- ALTER TABLE public.task RENAME COLUMN criteria TO feedback_focus;
-- COMMENT ON COLUMN public.task.feedback_focus IS 'Vom Lehrer definierter Fokus für das KI-Feedback (z.B. spezifische Aspekte, die im Feedback behandelt werden sollen). Ursprünglich "criteria".';