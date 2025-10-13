-- Migration: Füge eine Spalte für die KI-Kriterienanalyse zur Submission-Tabelle hinzu

-- Füge die neue Spalte 'ai_criteria_analysis' vom Typ TEXT hinzu.
-- Sie kann NULL sein, falls die Analyse fehlschlägt oder nicht durchgeführt wird.
ALTER TABLE public.submission
  ADD COLUMN ai_criteria_analysis TEXT;

-- Optional: Füge einen Kommentar zur Spalte hinzu
COMMENT ON COLUMN public.submission.ai_criteria_analysis IS 'Die detaillierte, von der KI generierte Analyse der Schülerlösung basierend auf den Lehrer-Kriterien.';

-- Optional: Passe den Kommentar für ai_grade an, um klarzustellen, dass es ein Vorschlag ist
COMMENT ON COLUMN public.submission.ai_grade IS 'Von der KI generierter Bewertungsvorschlag (z.B. 0-15 Punkte) für die Lehrkraft (intern).';