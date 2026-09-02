import { describe, expect, it } from "vitest";

import {
  submissionDraftStorageKey
} from "./submission-drafts";

describe("submission drafts", () => {
  it("builds a learner, course and task scoped storage key", () => {
    expect(
      submissionDraftStorageKey({ learnerSub: "student/2", courseId: "course-1", taskId: "task-1", mode: "text" })
    ).toBe("gustav.learning.submission-draft:student%2F2:course-1:task-1:text");
  });
});
