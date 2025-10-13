-- Sauber-Fix: Benenne solution_data zu submission_data um für Konsistenz

-- Spalte umbenennen
ALTER TABLE submission RENAME COLUMN solution_data TO submission_data;

-- Index eventuell auch umbenennen (falls vorhanden)
-- Prüfe erst ob Index existiert
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_submission_solution_data') THEN
        ALTER INDEX idx_submission_solution_data RENAME TO idx_submission_submission_data;
    END IF;
END $$;
