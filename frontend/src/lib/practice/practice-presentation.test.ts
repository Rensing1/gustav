import { describe, expect, it } from "vitest";

import {
  practiceSessionNeedsPolling,
  practiceClassificationLabel,
  practiceDueLabel,
  practiceErrorMessage
} from "./practice-presentation";

describe("practice presentation labels", () => {
  it("uses learner-facing classification language", () => {
    expect(practiceClassificationLabel("secure")).toBe("Sicher beantwortet");
    expect(practiceClassificationLabel("partial")).toBe("Teilweise beantwortet");
    expect(practiceClassificationLabel("insufficient")).toBe("Noch nicht sicher");
    expect(practiceClassificationLabel(null)).toBe("Rückmeldung");
  });

  it("describes due dates without exposing scheduler timestamps", () => {
    const now = "2026-08-12T12:00:00.000Z";
    expect(practiceDueLabel("2026-08-12T11:59:00.000Z", now)).toBe("Jetzt wiederholen");
    expect(practiceDueLabel("2026-08-13T12:00:00.000Z", now)).toBe("Nächste Wiederholung morgen");
    expect(practiceDueLabel("2026-08-14T12:00:00.000Z", now)).toBe("Nächste Wiederholung in 2 Tagen");
    expect(practiceDueLabel("2026-10-12T12:00:00.000Z", now)).toBe("Nächste Wiederholung in 3 Monaten");
    expect(practiceDueLabel(null, now)).toBeNull();
  });

  it("turns stable backend codes into learner-facing messages", () => {
    expect(practiceErrorMessage("practice_feedback_pending")).toBe("Die Rückmeldung ist noch nicht fertig.");
    expect(practiceErrorMessage("practice_request_failed")).toBe("Die Aktion konnte nicht abgeschlossen werden. Bitte versuche es erneut.");
    expect(practiceErrorMessage("unexpected_internal_code")).toBe("Die Aktion konnte nicht abgeschlossen werden. Bitte versuche es erneut.");
  });

  it.each([
    ["awaiting_analysis", "pending", true],
    ["awaiting_analysis", "completed", true],
    ["awaiting_analysis", "failed", true],
    ["active", "pending", true],
    ["feedback", "completed", false],
    ["active", "failed", false],
    [null, null, false]
  ] as const)(
    "polls item status %s with attempt status %s: %s",
    (itemStatus, attemptStatus, expected) => {
      expect(practiceSessionNeedsPolling(itemStatus, attemptStatus)).toBe(expected);
    }
  );
});
