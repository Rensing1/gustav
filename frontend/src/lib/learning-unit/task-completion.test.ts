import { describe, expect, it } from "vitest";

import type { LearningSubmission, LearningTask } from "$lib/types/learning";
import {
  h5pProgressLabel,
  latestH5PScore,
  taskIsComplete
} from "./task-completion";

function h5pTask(overrides: Partial<LearningTask> = {}): LearningTask {
  return {
    id: "task-h5p",
    instruction_md: "Ordne zu.",
    criteria: [],
    kind: "h5p",
    h5p: { content_id: "content-1" },
    h5p_completed: false,
    score_raw: null,
    score_max: null,
    ...overrides
  };
}

function h5pSubmission(raw: number, max: number): LearningSubmission {
  return {
    id: `submission-${raw}-${max}`,
    intent: "submit",
    kind: "h5p",
    attempt_nr: 1,
    created_at: "2026-09-24T08:00:00Z",
    analysis_status: "completed",
    score_raw: raw,
    score_max: max
  };
}

describe("task completion", () => {
  it("does not treat a partial H5P submission as completion", () => {
    const task = h5pTask({ has_submission: true, score_raw: 0, score_max: 1 });
    expect(taskIsComplete(task, [h5pSubmission(0, 1)])).toBe(false);
    expect(h5pProgressLabel(task, [h5pSubmission(0, 1)]))
      .toBe("Noch nicht abgeschlossen · zuletzt 0/1 Punkte");
  });

  it("retains completion after a newer partial H5P attempt", () => {
    const task = h5pTask({
      has_submission: true,
      h5p_completed: true,
      score_raw: 0,
      score_max: 1
    });
    expect(taskIsComplete(task, [h5pSubmission(0, 1)])).toBe(true);
    expect(latestH5PScore(task, [h5pSubmission(0, 1)])).toEqual({ raw: 0, max: 1 });
    expect(h5pProgressLabel(task, [h5pSubmission(0, 1)]))
      .toBe("Abgeschlossen · zuletzt 0/1 Punkte");
  });

  it("distinguishes an untouched H5P task from a partial attempt", () => {
    expect(h5pProgressLabel(h5pTask(), [])).toBe("Noch nicht bearbeitet");
  });

  it("keeps native final-submission semantics", () => {
    const task: LearningTask = {
      id: "task-native",
      instruction_md: "Erkläre.",
      criteria: [],
      kind: "native",
      latest_final_submission_at: "2026-09-24T08:00:00Z"
    };
    expect(taskIsComplete(task, [])).toBe(true);
  });

  it("counts the existing 0/0 H5P special case as complete", () => {
    expect(taskIsComplete(h5pTask(), [h5pSubmission(0, 0)])).toBe(true);
  });
});
