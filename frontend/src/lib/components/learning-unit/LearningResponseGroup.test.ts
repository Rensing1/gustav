import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import LearningResponseGroup from "./LearningResponseGroup.svelte";
import type { LearningSubmission } from "$lib/types/learning";

const submission: LearningSubmission = {
  id: "submission-1",
  attempt_nr: 1,
  kind: "text",
  intent: "submit",
  created_at: "2026-04-05 10:00",
  analysis_status: "completed",
  text_body: "Meine Lösung",
  feedback_md: "## Rückmeldung\n\nGut strukturiert.",
  analysis_json: {
    schema: "learning.v1",
    score: 8,
    text: "Stabil",
    criteria_results: []
  }
};

describe("LearningResponseGroup", () => {
  it("renders submission, feedback and evaluation as related disclosure blocks", () => {
    render(LearningResponseGroup, {
      props: {
        submission
      }
    });

    expect(screen.getByText("Abgabe")).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByText("Bewertung")).toBeInTheDocument();
  });
});
