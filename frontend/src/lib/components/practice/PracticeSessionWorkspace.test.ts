import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import PracticeSessionWorkspace from "./PracticeSessionWorkspace.svelte";

vi.mock("$app/navigation", () => ({ invalidateAll: vi.fn() }));

const session = {
  id: "session-1",
  mode: "due" as const,
  status: "active" as const,
  started_at: "2026-08-12T12:00:00Z",
  ended_at: null,
  end_reason: null,
  total_items: 2,
  completed_items: 0,
  summary: null,
  current_item: {
    id: "item-1",
    course_id: "course-1",
    practice_module_id: "module-1",
    module_title: "EVA-Prinzip",
    task_id: "task-1",
    position: 1,
    status: "feedback" as const,
    presentation_number: 1 as const,
    kind: "native" as const,
    instruction_md: "**Erkläre** das EVA-Prinzip.",
    h5p_content_id: null,
    latest_attempt_id: "attempt-1"
  }
};

describe("PracticeSessionWorkspace", () => {
  it("counts the current answered item in visible progress while feedback is shown", () => {
    render(PracticeSessionWorkspace, {
      props: {
        session,
        attempt: {
          id: "attempt-1",
          status: "completed",
          classification: "partial",
          fulfillment: 0.7,
          feedback_md: "Guter Anfang.",
          due_at: null
        },
        attemptKey: "key-1",
        solution: null,
        nowIso: "2026-08-12T12:00:00Z"
      }
    });

    expect(screen.getByRole("progressbar", { name: "50 Prozent bearbeitet" })).toHaveValue(1);
    expect(screen.getByText("Erkläre", { exact: false })).toBeVisible();
    expect(document.body.textContent).not.toContain("criteria");
  });

  it("allows a new submission after a technical analysis failure", () => {
    render(PracticeSessionWorkspace, {
      props: {
        session: {
          ...session,
          current_item: {
            ...session.current_item,
            status: "active"
          }
        },
        attempt: {
          id: "attempt-1",
          status: "failed",
          classification: null,
          fulfillment: null,
          feedback_md: null,
          due_at: null
        },
        attemptKey: "fresh-key",
        solution: null,
        nowIso: "2026-08-12T12:00:00Z"
      }
    });

    expect(screen.getByText("Die Auswertung konnte nicht abgeschlossen werden")).toBeVisible();
    expect(screen.getByLabelText("Deine Antwort")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Antwort prüfen" })).toBeEnabled();
  });
});
