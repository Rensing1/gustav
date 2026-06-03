export const MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE =
  "Der Verlauf konnte nicht geladen werden. Bitte öffne die Lerneinheit erneut.";

export function isUsableLearningRouteId(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }

  const trimmed = value.trim();
  return Boolean(trimmed && trimmed.toLowerCase() !== "undefined" && trimmed.toLowerCase() !== "null");
}

export function buildLearningSubmissionHistoryUrl(courseId: unknown, taskId: unknown): string | null {
  if (!isUsableLearningRouteId(courseId) || !isUsableLearningRouteId(taskId)) {
    return null;
  }

  return `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions?limit=10&offset=0`;
}
