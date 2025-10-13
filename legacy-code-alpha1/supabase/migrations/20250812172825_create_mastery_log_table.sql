-- 1. Erforderliche Hilfsfunktionen erstellen

-- HINWEIS: is_user_role() existiert bereits seit Migration 20250414143203.

-- Funktion, um zu prüfen, ob ein Lehrer einem Kurs zugeordnet ist
CREATE OR REPLACE FUNCTION public.is_teacher_in_course(p_teacher_id UUID, p_course_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM public.course_teacher
    WHERE course_id = p_course_id AND teacher_id = p_teacher_id
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- Berechtigungen für die neue Funktion
GRANT EXECUTE ON FUNCTION public.is_teacher_in_course(UUID, UUID) TO authenticated;

-- 2. Die eigentliche Tabelle erstellen
CREATE TABLE public.mastery_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.task(id) ON DELETE CASCADE,
    review_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    time_since_last_review REAL NOT NULL, -- in Tagen
    stability_before REAL NOT NULL,
    difficulty_before REAL NOT NULL,
    recall_outcome SMALLINT NOT NULL, -- 1 für richtig, 0 für falsch
    q_cor REAL, -- Korrektheit (0-1)
    q_flu REAL, -- Flüssigkeit (0-1)
    q_com REAL, -- Vollständigkeit (0-1)
    q_err VARCHAR(50), -- Fehlerkategorie
    time_taken_seconds INT, -- Bearbeitungszeit in Sekunden
    rationale TEXT -- Begründung der KI
);


-- 3. Row-Level Security für die neue Tabelle aktivieren
ALTER TABLE public.mastery_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Benutzer können ihre eigenen Log-Einträge sehen" 
ON public.mastery_log FOR SELECT
USING (auth.uid() = user_id);


CREATE POLICY "Lehrer können die Log-Einträge ihrer Schüler sehen" 
ON public.mastery_log FOR SELECT
USING (
  public.is_user_role(auth.uid(), 'teacher') AND
  EXISTS (
    SELECT 1
    FROM public.course_student cs
    JOIN public.task t ON t.id = mastery_log.task_id
    JOIN public.unit_section us ON t.section_id = us.id
    JOIN public.course_learning_unit_assignment clua ON us.unit_id = clua.unit_id
    WHERE cs.student_id = mastery_log.user_id
      AND cs.course_id = clua.course_id
      AND public.is_teacher_in_course(auth.uid(), cs.course_id)
  )
);

-- Kein INSERT, UPDATE, DELETE für normale Nutzer erlaubt. Dies wird nur serverseitig durchgeführt.
CREATE POLICY "Keine direkten Schreib-Operationen auf Logs erlaubt" 
ON public.mastery_log FOR ALL
USING (false)
WITH CHECK (false);