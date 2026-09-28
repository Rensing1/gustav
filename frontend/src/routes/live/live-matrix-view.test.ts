import { describe, expect, it } from "vitest";

import type { LiveSummaryPayload } from "$lib/types/home";
import { buildLiveMatrixView } from "./live-matrix-view";

const summary: LiveSummaryPayload = {
  cursor: "2026-09-27T10:00:00Z",
  tasks: [
    { id: "learn-1", instruction_md: "L1", position: 1, kind: "native", section_id: "section-a", section_title: "Grundlagen", module_id: "module-a", module_kind: "learning" },
    { id: "practice-1", instruction_md: "P1", position: 1, kind: "native", section_id: "section-p", section_title: "Wiederholen", module_id: "module-p", module_kind: "practice" },
    { id: "learn-2", instruction_md: "L2", position: 2, kind: "native", section_id: "section-a", section_title: "Grundlagen", module_id: "module-a", module_kind: "learning" },
  ],
  practice_modules: [
    { id: "module-p", section_id: "section-p", title: "Wiederholen", task_ids: ["practice-1"] }
  ],
  rows: [
    {
      student: { sub: "student-1", name: "Ada" },
      tasks: [
        { task_id: "learn-1", has_submission: true, average_score: 8.5 },
        { task_id: "practice-1", has_submission: true, average_score: 7 },
        { task_id: "learn-2", has_submission: false, average_score: null }
      ],
      practice: [
        { module_id: "module-p", status: "due", task_count: 1, due_tasks_count: 1, secure_tasks_count: 0, partial_tasks_count: 0, insufficient_tasks_count: 0, latest_activity_at: null, next_due_at: null }
      ]
    }
  ]
};

describe("Live matrix view model", () => {
  it.each([[0, "low"], [3.9, "low"], [4, "mid"], [7.9, "mid"], [8, "high"], [10, "high"]])("uses the existing threshold for score %s", (score, tone) => {
    const input = structuredClone(summary);
    input.rows[0].tasks[0].average_score = Number(score);
    expect(buildLiveMatrixView(input).rows[0].learningCells[0].tone).toBe(tone);
  });

  it("distinguishes an unscored submission and an empty roster", () => {
    const input = structuredClone(summary);
    input.rows[0].tasks[0].average_score = null;
    expect(buildLiveMatrixView(input).rows[0].learningCells[0]).toMatchObject({ label: "•", tone: "submitted" });
    input.rows = [];
    expect(buildLiveMatrixView(input).rows).toEqual([]);
  });

  it("keeps practice tasks out of learning groups and summarizes individual practice tasks", () => {
    const view = buildLiveMatrixView(summary);

    expect(view.learningGroups).toEqual([
      expect.objectContaining({ id: "section-a", title: "Grundlagen", taskIds: ["learn-1", "learn-2"] })
    ]);
    expect(view.rows[0].learningCells.map((cell) => cell.task.id)).toEqual(["learn-1", "learn-2"]);
    expect(view.rows[0].learningSummary).toEqual({
      completed: 1,
      total: 2,
      rated: 1,
      average: 8.5,
      averageLabel: "8,5",
      tone: "high"
    });
    expect(view.rows[0].practiceSummary).toEqual({ due: 1, secure: 0 });
  });

  it("normalizes rated H5P learning tasks but excludes practice and ungraded submissions", () => {
    const input = structuredClone(summary);
    input.tasks[2].kind = "h5p";
    input.rows[0].tasks[2] = {
      task_id: "learn-2",
      has_submission: true,
      average_score: null,
      score_raw: 3,
      score_max: 4
    };

    expect(buildLiveMatrixView(input).rows[0].learningSummary).toEqual({
      completed: 2,
      total: 2,
      rated: 2,
      average: 8,
      averageLabel: "8",
      tone: "high"
    });
  });

  it("shows no invented average when submitted learning tasks are ungraded", () => {
    const input = structuredClone(summary);
    input.rows[0].tasks[0].average_score = null;

    expect(buildLiveMatrixView(input).rows[0].learningSummary).toMatchObject({
      completed: 1,
      total: 2,
      rated: 0,
      average: null,
      averageLabel: "–",
      tone: "empty"
    });
  });

  it("derives compact accessible score labels without hiding open state", () => {
    const view = buildLiveMatrixView(summary);

    expect(view.rows[0].learningCells[0]).toMatchObject({ label: "8,5", tone: "high" });
    expect(view.rows[0].learningCells[1]).toMatchObject({ label: "–", tone: "empty" });
  });
});
