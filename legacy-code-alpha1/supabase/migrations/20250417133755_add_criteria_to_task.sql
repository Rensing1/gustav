-- Migration: Füge eine Spalte für Bewertungskriterien zur Task-Tabelle hinzu

-- Füge die neue Spalte 'criteria' vom Typ TEXT hinzu.
-- Sie kann NULL sein, falls keine Kriterien angegeben werden.
ALTER TABLE public.task
  ADD COLUMN criteria TEXT;

-- Optional: Füge einen Kommentar zur Spalte hinzu (gut für die Dokumentation)
COMMENT ON COLUMN public.task.criteria IS 'Vom Lehrer definierte Bewertungskriterien für diese Aufgabe (z.B. als Markdown-Liste). Wird als Kontext für die KI-Bewertung verwendet.';