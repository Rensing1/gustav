-- Entferne die alten, nicht mehr benötigten SM-2 Spalten
ALTER TABLE public.student_mastery_progress
DROP COLUMN IF EXISTS ease_factor,
DROP COLUMN IF EXISTS current_interval,
DROP COLUMN IF EXISTS repetition_count,
DROP COLUMN IF EXISTS learning_step_index,
DROP COLUMN IF EXISTS relearning_step_index;

-- Füge die neuen DSRKI-Spalten hinzu
ALTER TABLE public.student_mastery_progress
ADD COLUMN stability REAL,
ADD COLUMN difficulty REAL;

-- Setze Standardwerte für die neuen Spalten für bestehende Zeilen, falls es welche gibt.
-- Dies stellt sicher, dass wir keine NULL-Werte haben, wenn der neue Algorithmus
-- auf bereits existierende Fortschritts-Einträge trifft.
-- Die Startwerte (z.B. D=5) können hier noch angepasst werden.
UPDATE public.student_mastery_progress
SET 
    stability = 0.1, -- Eine sehr geringe Start-Stabilität
    difficulty = 5.0   -- Eine mittlere Start-Schwierigkeit
WHERE stability IS NULL OR difficulty IS NULL;

-- Mache die Spalten NOT NULL, nachdem die Standardwerte gesetzt wurden.
-- Wir setzen auch einen Standardwert für zukünftige INSERTS.
ALTER TABLE public.student_mastery_progress
ALTER COLUMN stability SET NOT NULL,
ALTER COLUMN stability SET DEFAULT 0.1,
ALTER COLUMN difficulty SET NOT NULL,
ALTER COLUMN difficulty SET DEFAULT 5.0;
