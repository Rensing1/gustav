-- supabase/migrations/20250813094436_create_rpc_for_ai_submission_update.sql

-- Erstellt eine SECURITY DEFINER Funktion, um Einreichungen sicher
-- durch den AI-Backend-Prozess aktualisieren zu können, ohne den
-- Service Role Key direkt im App-Code zu verwenden.

CREATE OR REPLACE FUNCTION public.update_submission_from_ai(
    submission_id_in uuid,
    criteria_analysis_in jsonb,
    feedback_in text,
    rating_suggestion_in text,
    feed_back_text_in text,
    feed_forward_text_in text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
-- Set a secure search_path: only include extensions and public schema
SET search_path = extensions, public
AS $$
BEGIN
  UPDATE public.submission
  SET
    ai_criteria_analysis = criteria_analysis_in,
    ai_feedback = feedback_in,
    feedback_generated_at = now(),
    ai_grade = rating_suggestion_in,
    grade_generated_at = now(),
    feed_back_text = feed_back_text_in,
    feed_forward_text = feed_forward_text_in
  WHERE id = submission_id_in;
END;
$$;

-- Gib der Rolle 'service_role', die von vertrauenswürdigen Backend-Systemen
-- wie dem AI-Feedback-Prozess verwendet wird, die Berechtigung, diese
-- spezifische Funktion auszuführen.
GRANT EXECUTE
ON FUNCTION public.update_submission_from_ai(uuid, jsonb, text, text, text, text)
TO service_role;
