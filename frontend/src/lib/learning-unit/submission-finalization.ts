export type SubmissionIntent = "feedback" | "submit";

export type SubmissionAttempt =
  | { accepted: false }
  | {
      accepted: true;
      taskId: string;
      intent: SubmissionIntent;
      statusMessage: string;
    };

/**
 * Starts one visible submission attempt and rejects concurrent form requests.
 * The caller owns the pending task id and clears it after success or failure.
 */
export function beginSubmissionAttempt(
  pendingTaskId: string | null,
  taskId: string,
  intent: SubmissionIntent
): SubmissionAttempt {
  if (pendingTaskId) {
    return { accepted: false };
  }
  return {
    accepted: true,
    taskId,
    intent,
    statusMessage: intent === "submit" ? "Abgabe wird verarbeitet ..." : "Rückmeldung wird erstellt ..."
  };
}

/** Converts stable backend error codes into actionable learner-facing German. */
export function finalSubmissionFailureMessage(detail: string | null | undefined, status: number): string {
  if (detail === "draft_not_ready") {
    return "Die Rückmeldung wird noch verarbeitet. Bitte versuche die endgültige Abgabe gleich noch einmal.";
  }
  if (detail === "draft_missing") {
    return "Es gibt noch keinen rückgemeldeten Entwurf. Hole zuerst eine Rückmeldung ein.";
  }
  if (detail === "max_attempts_exceeded") {
    return "Für diese Aufgabe sind keine weiteren endgültigen Abgaben möglich.";
  }
  if (status === 503 || detail === "submission_persistence_unavailable") {
    return "Die endgültige Abgabe konnte wegen einer vorübergehenden Störung nicht gespeichert werden. Bitte versuche es erneut.";
  }
  if (status === 403) {
    return "Du bist für diese Aufgabe nicht zur endgültigen Abgabe berechtigt.";
  }
  return "Die endgültige Abgabe konnte nicht gespeichert werden. Bitte versuche es erneut.";
}
