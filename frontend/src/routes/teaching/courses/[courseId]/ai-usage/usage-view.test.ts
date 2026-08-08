import { describe, expect, it } from "vitest";

import { courseUsageForBrowser, usageLoadErrorMessage } from "./usage-view";

describe("course AI usage browser view", () => {
  it("whitelists course counters and merges hidden API dimensions", () => {
    const view = courseUsageForBrowser({
      course: { id: "course-1", title: "Mathematik", href: "/teaching/courses/course-1", members_count: 1 },
      totals: {
        input_tokens: 20,
        output_tokens: 5,
        total_tokens: 25,
        known_events: 2,
        unknown_events: 0,
        breakdown: [
          {
            model: "model-a",
            stage: "feedback",
            modality: "text",
            call_kind: "primary",
            input_tokens: 12,
            output_tokens: 3,
            total_tokens: 15,
            known_events: 1,
            unknown_events: 0,
            provider_payload: "must-not-reach-browser"
          },
          {
            model: "model-a",
            stage: "feedback",
            modality: "visual",
            call_kind: "repair",
            input_tokens: 8,
            output_tokens: 2,
            total_tokens: 10,
            known_events: 1,
            unknown_events: 0
          }
        ]
      },
      learners: [{ student: { sub: "student-1", name: "Lena Beispiel" } }]
    });

    expect(view).toEqual({
      course: { id: "course-1", title: "Mathematik", href: "/teaching/courses/course-1" },
      totals: {
        input_tokens: 20,
        output_tokens: 5,
        total_tokens: 25,
        known_events: 2,
        unknown_events: 0,
        breakdown: [
          {
            model: "model-a",
            stage: "feedback",
            input_tokens: 20,
            output_tokens: 5,
            total_tokens: 25
          }
        ]
      }
    });
    expect(JSON.stringify(view)).not.toContain("Lena Beispiel");
    expect(JSON.stringify(view)).not.toContain("must-not-reach-browser");
  });

  it("turns private backend failures into understandable messages", () => {
    expect(usageLoadErrorMessage(422)).toBe("Der gewählte Zeitraum ist ungültig.");
    expect(usageLoadErrorMessage(503)).toBe("Die KI-Nutzung konnte nicht geladen werden. Bitte versuche es erneut.");
  });
});
