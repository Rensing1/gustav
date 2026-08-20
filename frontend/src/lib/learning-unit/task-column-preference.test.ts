import { describe, expect, it } from "vitest";

import {
  MAX_TASK_COLUMN_RATIO,
  MIN_TASK_COLUMN_RATIO,
  readTaskColumnRatio,
  removeTaskColumnRatio,
  taskColumnPreferenceStorageKey,
  writeTaskColumnRatio
} from "./task-column-preference";

describe("learner task column preference", () => {
  it("uses one account-scoped key across courses and units", () => {
    expect(taskColumnPreferenceStorageKey("student/sub")).toBe(
      "gustav.learning.task-column-ratio:student%2Fsub"
    );
    expect(taskColumnPreferenceStorageKey(null)).toBeNull();
  });

  it("round-trips a versioned ratio without storing learning content", () => {
    const storage = new Map<string, string>();

    writeTaskColumnRatio(storage, "student-1", 58);

    expect(JSON.parse(storage.get("gustav.learning.task-column-ratio:student-1") ?? "null")).toEqual({
      version: 1,
      taskColumnRatio: 58
    });
    expect(readTaskColumnRatio(storage, "student-1")).toBe(58);
  });

  it("clamps committed values to the usable pane range", () => {
    const storage = new Map<string, string>();

    writeTaskColumnRatio(storage, "student-1", 5);
    expect(readTaskColumnRatio(storage, "student-1")).toBe(MIN_TASK_COLUMN_RATIO);

    writeTaskColumnRatio(storage, "student-1", 95);
    expect(readTaskColumnRatio(storage, "student-1")).toBe(MAX_TASK_COLUMN_RATIO);
  });

  it("falls back to automatic layout for malformed, stale or unavailable storage", () => {
    const key = "gustav.learning.task-column-ratio:student-1";
    const storage = new Map<string, string>();

    storage.set(key, "{invalid");
    expect(readTaskColumnRatio(storage, "student-1")).toBeNull();

    storage.set(key, JSON.stringify({ version: 2, taskColumnRatio: 50 }));
    expect(readTaskColumnRatio(storage, "student-1")).toBeNull();

    storage.set(key, JSON.stringify({ version: 1, taskColumnRatio: Number.NaN }));
    expect(readTaskColumnRatio(storage, "student-1")).toBeNull();

    expect(
      readTaskColumnRatio(
        {
          getItem() {
            throw new Error("storage unavailable");
          }
        },
        "student-1"
      )
    ).toBeNull();
  });

  it("removes the preference when the learner resets the presentation", () => {
    const storage = new Map<string, string>();
    writeTaskColumnRatio(storage, "student-1", 56);

    removeTaskColumnRatio(storage, "student-1");

    expect(readTaskColumnRatio(storage, "student-1")).toBeNull();
  });
});
