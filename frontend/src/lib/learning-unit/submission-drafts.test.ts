import { describe, expect, it } from "vitest";

import {
  clearSubmissionDraft,
  submissionDraftStorageKey,
  type SubmissionDraftStorage
} from "./submission-drafts";

function memoryStorage(entries: Record<string, string>): SubmissionDraftStorage {
  const values = new Map(Object.entries(entries));
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value)
  };
}

describe("submission drafts", () => {
  it("builds a learner, course and task scoped storage key", () => {
    expect(
      submissionDraftStorageKey({ learnerSub: "student/2", courseId: "course-1", taskId: "task-1", mode: "text" })
    ).toBe("gustav.learning.submission-draft:student%2F2:course-1:task-1:text");
  });

  it("clears only the finalized task draft", () => {
    const firstKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    const secondKey = "gustav.learning.submission-draft:student-2:course-1:task-2:text";
    const storage = memoryStorage({ [firstKey]: "Finaler Text", [secondKey]: "Anderer Entwurf" });

    clearSubmissionDraft(storage, {
      learnerSub: "student-2",
      courseId: "course-1",
      taskId: "task-1",
      mode: "text"
    });

    expect(storage.getItem(firstKey)).toBeNull();
    expect(storage.getItem(secondKey)).toBe("Anderer Entwurf");
  });
});
