import { describe, expect, it } from "vitest";

import {
  beginSubmissionAttempt,
  finalSubmissionFailureMessage
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
    expect(beginSubmissionAttempt("task-1", "task-1", "submit")).toEqual({ accepted: false });
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
