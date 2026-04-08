import { render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import LearningSubmissionWorkspace from "./LearningSubmissionWorkspace.svelte";
import type { LearningSubmission, LearningTask } from "$lib/types/learning";

const nativeTask: LearningTask = {
  id: "task-1",
  instruction_md: "Beschreibe die Lösung.",
  criteria: ["Kriterium"],
  kind: "native"
};

function feedbackSubmission(overrides: Partial<LearningSubmission> = {}): LearningSubmission {
  return {
    id: "submission-1",
    intent: "feedback",
    attempt_nr: 1,
    kind: "text",
    created_at: "2026-04-04T10:00:00+00:00",
    analysis_status: "completed",
    text_body: "Mein erster Entwurf",
    feedback_md: "Bitte strukturiere den Text klarer.",
    analysis_json: null,
    ...overrides
  };
}

describe("LearningSubmissionWorkspace", () => {
  it("renders separate feedback and final submit actions in upload mode", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "upload"
      }
    });

    expect(screen.getByRole("button", { name: "Rückmeldung einholen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
    expect(screen.getByText("Datei auswählen")).toBeInTheDocument();
  });

  it("renders inline feedback when a feedback request has just completed", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "upload",
        initialHistoryLoaded: true,
        initialHistory: [feedbackSubmission()],
        message: "feedback"
      }
    });

    expect(screen.getByText("Neueste Rückmeldung")).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByText("Bitte strukturiere den Text klarer.")).toBeInTheDocument();
  });

  it("distinguishes feedback and final submissions in history", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission(),
          feedbackSubmission({
            id: "submission-2",
            intent: "submit",
            attempt_nr: 2,
            created_at: "2026-04-04T11:00:00+00:00",
            feedback_md: "Abgegeben."
          })
        ]
      }
    });

    const historyEntries = document.querySelectorAll(".learning-submission-history__entry");
    expect(historyEntries).toHaveLength(2);
    expect(within(historyEntries[0] as HTMLElement).getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(within(historyEntries[1] as HTMLElement).getAllByText("Abgabe").length).toBeGreaterThan(0);
  });

  it("renders markdown for submission, feedback and evaluation history in the learner workspace", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            text_body: "## Lösung\n\n**Antwort**<br>mit Umbruch\n\n1. Schritt\n2. Schritt\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
            feedback_md: "## Rückmeldung\n\n*Gut* gemacht.\n\n- Präzise",
            analysis_json: {
              schema: "learning.v1",
              score: 8,
              text: "Stabil",
              criteria_results: [
                {
                  criterion: "Kriterium",
                  explanation_md: "[Hinweis](https://example.com)\n\n| Name | Wert |\n| --- | --- |\n| A | B |"
                }
              ]
            }
          })
        ]
      }
    });

    expect(document.querySelector(".learning-submission-history .markdown-prose h2")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose strong")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose em")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose br")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose ol")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose table")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Hinweis" })).toHaveAttribute("href", "https://example.com");
  });
});
