import { describe, expect, it } from "vitest";

import type { LearningSubmission, LearningTask } from "$lib/types/learning";
import {
  completionReturnDestination,
  learnerReturnLabel
} from "./learner-return-navigation";

function task(id: string, latestFinalSubmissionAt: string | null = null): LearningTask {
  return {
    id,
    instruction_md: `Bearbeite ${id}.`,
    criteria: [],
    kind: "native",
    latest_final_submission_at: latestFinalSubmissionAt
  };
}

function feedbackSubmission(): LearningSubmission {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    attempt_nr: 1,
    kind: "text",
    intent: "feedback",
    created_at: "2026-09-03T08:00:00Z",
    analysis_status: "completed"
  };
}

describe("learner return navigation", () => {
  it("returns to the module while another task there is still open", () => {
    expect(completionReturnDestination({
      unitType: "modular",
      currentTaskId: "task-1",
      moduleTasks: [task("task-1"), task("task-2")],
      historyByTask: {}
    })).toBe("module");
  });

  it("returns to the learning path when every other module task is finalized", () => {
    expect(completionReturnDestination({
      unitType: "modular",
      currentTaskId: "task-1",
      moduleTasks: [task("task-1"), task("task-2", "2026-09-02T08:00:00Z")],
      historyByTask: {}
    })).toBe("learningPath");
  });

  it("treats formative feedback without final submission as an open task", () => {
    expect(completionReturnDestination({
      unitType: "modular",
      currentTaskId: "task-1",
      moduleTasks: [task("task-1"), task("task-2")],
      historyByTask: { "task-2": [feedbackSubmission()] }
    })).toBe("module");
  });

  it("uses the contents destination for linear units", () => {
    expect(completionReturnDestination({
      unitType: "linear",
      currentTaskId: "task-1",
      moduleTasks: [task("task-1")],
      historyByTask: {}
    })).toBe("contents");
    expect(learnerReturnLabel("contents")).toBe("Zurück zu den Inhalten");
  });
});
