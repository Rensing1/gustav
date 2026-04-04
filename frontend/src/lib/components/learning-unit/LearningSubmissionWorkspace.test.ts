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
});
