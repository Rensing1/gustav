-- supabase/migrations/20250813100308_create_rpc_for_teacher_override.sql

-- Erstellt eine SECURITY DEFINER Funktion, die es einem Lehrer erlaubt,
-- eine Einreichung zu überschreiben, ABER NUR, wenn der Lehrer auch
-- tatsächlich die Berechtigung für den zugehörigen Kurs hat.

CREATE OR REPLACE FUNCTION public.update_submission_by_teacher(
    submission_id_in uuid,
    teacher_feedback_in text,
    teacher_grade_in text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
-- Set a secure search_path
SET search_path = extensions, public
AS $$
DECLARE
    is_authorized boolean;
BEGIN
    -- Schritt 1: Überprüfe, ob der aufrufende Benutzer (Lehrer) die Berechtigung hat.
    -- Ein Lehrer ist berechtigt, wenn er in einem Kurs unterrichtet, der die Lerneinheit
    -- enthält, zu der die Aufgabe der Einreichung gehört.
    SELECT EXISTS (
        SELECT 1
        FROM public.submission s
        -- JOIN über die Aufgaben- und Einheiten-Hierarchie zum Kurs
        JOIN public.task t ON s.task_id = t.id
        JOIN public.unit_section us ON t.section_id = us.id
        JOIN public.course_learning_unit_assignment clua ON us.unit_id = clua.unit_id
        -- JOIN zur Lehrer-Tabelle, um die Berechtigung zu prüfen
        JOIN public.course_teacher ct ON clua.course_id = ct.course_id
        WHERE
            s.id = submission_id_in
            AND ct.teacher_id = auth.uid() -- auth.uid() ist der aufrufende Benutzer
    ) INTO is_authorized;

    -- Schritt 2: Wenn nicht berechtigt, wirf einen Fehler.
    IF NOT is_authorized THEN
        RAISE EXCEPTION 'Unauthorized: Sie haben keine Berechtigung, diese Einreichung zu bearbeiten.';
    END IF;

    -- Schritt 3: Wenn berechtigt, führe das Update durch.
    UPDATE public.submission
    SET
        teacher_override_feedback = teacher_feedback_in,
        teacher_override_grade = teacher_grade_in,
        updated_at = now()
    WHERE id = submission_id_in;
END;
$$;

-- Gib allen authentifizierten Benutzern die Berechtigung, diese Funktion auszuführen.
-- Die Sicherheitsprüfung findet INNERHALB der Funktion statt.
GRANT EXECUTE
ON FUNCTION public.update_submission_by_teacher(uuid, text, text)
TO authenticated;
