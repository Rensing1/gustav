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
  it("nests qualitative criteria below feedback and keeps the submission separate", () => {
    render(LearningResponseGroup, {
      props: {
        submission: {
          ...submission,
          analysis_json: {
            schema: "learning.v1",
            criteria_results: [{ criterion: "Klarheit", score: 8, max_score: 10, explanation_md: "Gut erklärt." }]
          }
        }
      }
    });

    const group = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(Array.from(group.querySelectorAll(".learning-response-panel > summary"), (summary) => summary.textContent?.trim())).toEqual([
      "Rückmeldung",
      "Meine Abgabe"
    ]);
    expect(screen.getByText("Kriterien im Detail")).toBeInTheDocument();
    expect(screen.getByText("Gelungen")).toBeInTheDocument();
    expect(group.textContent).not.toContain("8/10");
  });

  it("omits empty feedback and evaluation disclosures", () => {
    render(LearningResponseGroup, {
      props: {
        submission: { ...submission, feedback_md: null, analysis_json: null }
      }
    });

    const group = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(Array.from(group.querySelectorAll("summary"), (summary) => summary.textContent?.trim())).toEqual(["Meine Abgabe"]);
    expect(screen.queryByText(/liegt noch keine/i)).toBeNull();
  });
});
