import { describe, expect, it } from "vitest";

import {
  beginSubmissionAttempt,
  finalSubmissionIdempotencyKey,
  finalSubmissionFailureMessage,
  normalizeReviewedSubmissionText,
  reviewedSubmissionBaseline,
  validatedFeedbackSubmissionId,
  validatedFinalSubmissionIdempotencyKey
} from "./submission-finalization";

describe("submission finalization", () => {
  it("starts final submission with an immediate visible pending state", () => {
    expect(beginSubmissionAttempt(null, "task-1", "submit")).toEqual({
      accepted: true,
      taskId: "task-1",
      intent: "submit",
      statusMessage: "Abgabe wird verarbeitet ..."
    });
  });

  it("rejects another attempt while a submission request is active", () => {
    expect(beginSubmissionAttempt("task-1", "task-1", "submit")).toEqual({
      accepted: false,
      statusMessage: "Diese Abgabe wird bereits verarbeitet."
    });
  });

  it("explains when another task currently owns the submission slot", () => {
    expect(beginSubmissionAttempt("task-1", "task-2", "submit")).toEqual({
      accepted: false,
      statusMessage: "Eine andere Abgabe wird bereits verarbeitet. Bitte warte kurz und versuche es dann erneut."
    });
  });

  it("derives one stable finalization key from the reviewed submission", () => {
    const submissionId = "123e4567-e89b-42d3-a456-426614174000";

    expect(finalSubmissionIdempotencyKey(submissionId)).toBe(`finalize-${submissionId}`);
    expect(finalSubmissionIdempotencyKey(submissionId)).toBe(`finalize-${submissionId}`);
    expect(finalSubmissionIdempotencyKey("not-a-submission")).toBeNull();
    expect(validatedFinalSubmissionIdempotencyKey(`finalize-${submissionId}`)).toBe(`finalize-${submissionId}`);
    expect(validatedFinalSubmissionIdempotencyKey("finalize-not-a-submission")).toBeNull();
  });

  it("accepts only a UUID for the reviewed feedback submission", () => {
    const submissionId = "123e4567-e89b-42d3-a456-426614174000";

    expect(validatedFeedbackSubmissionId(submissionId)).toBe(submissionId);
    expect(validatedFeedbackSubmissionId("submission-feedback")).toBeNull();
    expect(validatedFeedbackSubmissionId(null)).toBeNull();
  });

  it("creates one baseline only for completed feedback", () => {
    const baseline = reviewedSubmissionBaseline({
      id: "123e4567-e89b-42d3-a456-426614174000",
      attempt_nr: 1,
      intent: "feedback",
      kind: "text",
      analysis_status: "completed",
      created_at: "2026-09-01T08:00:00+00:00",
      text_body: "  Geprüfter Entwurf  "
    });

    expect(baseline).toEqual({
      submissionId: "123e4567-e89b-42d3-a456-426614174000",
      kind: "text",
      textBody: "  Geprüfter Entwurf  "
    });
    expect(reviewedSubmissionBaseline({
      id: "123e4567-e89b-42d3-a456-426614174001",
      attempt_nr: 2,
      intent: "feedback",
      kind: "text",
      analysis_status: "pending",
      created_at: "2026-09-01T08:01:00+00:00"
    })).toBeNull();
    expect(reviewedSubmissionBaseline({
      id: "submission-feedback",
      attempt_nr: 3,
      intent: "feedback",
      kind: "text",
      analysis_status: "completed",
      created_at: "2026-09-01T08:02:00+00:00",
      text_body: "Geprüfter Entwurf"
    })).toBeNull();
  });

  it("normalizes reviewed text exactly like the persistence boundary", () => {
    expect(normalizeReviewedSubmissionText(null)).toBe("");
    expect(normalizeReviewedSubmissionText("  Geprüfter Entwurf\n\n")).toBe("Geprüfter Entwurf");
    expect(normalizeReviewedSubmissionText("Absatz eins\n\nAbsatz zwei")).toBe("Absatz eins\n\nAbsatz zwei");
  });

  it.each([
    ["draft_not_ready", 409, "Die Rückmeldung wird noch verarbeitet. Bitte versuche die endgültige Abgabe gleich noch einmal."],
    ["draft_missing", 409, "Es gibt noch keinen rückgemeldeten Entwurf. Hole zuerst eine Rückmeldung ein."],
    ["max_attempts_exceeded", 400, "Für diese Aufgabe sind keine weiteren endgültigen Abgaben möglich."],
    [
      "submission_persistence_unavailable",
      503,
      "Die endgültige Abgabe konnte wegen einer vorübergehenden Störung nicht gespeichert werden. Bitte versuche es erneut."
    ]
  ])("maps %s to a learner-facing message", (detail, status, expected) => {
    expect(finalSubmissionFailureMessage(detail, status)).toBe(expected);
  });
});
