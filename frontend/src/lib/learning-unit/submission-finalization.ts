export type SubmissionIntent = "feedback" | "submit";

export type SubmissionAttempt =
  | { accepted: false; statusMessage: string }
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
    return {
      accepted: false,
      statusMessage:
        pendingTaskId === taskId
          ? "Diese Abgabe wird bereits verarbeitet."
          : "Eine andere Abgabe wird bereits verarbeitet. Bitte warte kurz und versuche es dann erneut."
    };
  }
  return {
    accepted: true,
    taskId,
    intent,
    statusMessage: intent === "submit" ? "Abgabe wird verarbeitet ..." : "Rückmeldung wird erstellt ..."
  };
}

const submissionIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Derives a retry-safe finalization key from the reviewed feedback submission. */
export function finalSubmissionIdempotencyKey(submissionId: string | null | undefined): string | null {
  const normalizedSubmissionId = submissionId?.trim() ?? "";
  if (!submissionIdPattern.test(normalizedSubmissionId)) {
    return null;
  }
  return `finalize-${normalizedSubmissionId}`;
}

/** Accepts only finalization keys produced from a valid feedback submission id. */
export function validatedFinalSubmissionIdempotencyKey(value: FormDataEntryValue | null): string | null {
  if (typeof value !== "string" || !value.startsWith("finalize-")) {
    return null;
  }
  const normalized = value.trim();
  const expected = finalSubmissionIdempotencyKey(normalized.slice("finalize-".length));
  return expected === normalized ? normalized : null;
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
