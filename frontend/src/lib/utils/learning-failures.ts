import type { LearningSubmission } from "$lib/types/learning";

export const imageTooComplexForProviderMessage =
  "Das Bild ist wahrscheinlich zu groß oder zu komplex. Bitte lade einen kleineren Ausschnitt hoch, zum Beispiel nur die Zeichnung statt des ganzen Bildschirms.";

export function learningSubmissionFailureMessage(
  submission: Pick<LearningSubmission, "feedback_last_error" | "vision_last_error">,
  fallback = "Die Auswertung konnte nicht erstellt werden."
): string {
  const reason = submission.feedback_last_error || submission.vision_last_error || "";
  if (reason === "image_too_complex_for_provider") {
    return imageTooComplexForProviderMessage;
  }
  return fallback;
}
