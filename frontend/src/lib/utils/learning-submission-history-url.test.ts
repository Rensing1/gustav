import { describe, expect, it } from "vitest";

import {
  buildLearningSubmissionHistoryUrl,
  isUsableLearningRouteId
} from "$lib/utils/learning-submission-history-url";

describe("learning submission history URL helpers", () => {
  it("builds the submission-history URL for usable route IDs", () => {
    expect(buildLearningSubmissionHistoryUrl("course 1", "task/1")).toBe(
      "/api/learning/courses/course%201/tasks/task%2F1/submissions?limit=10&offset=0"
    );
  });

  it.each([undefined, null, "", "   ", "undefined", " Undefined ", "null", " NULL "])(
    "rejects missing route ID value %s",
    (value) => {
      expect(isUsableLearningRouteId(value)).toBe(false);
      expect(buildLearningSubmissionHistoryUrl(value, "task-1")).toBeNull();
      expect(buildLearningSubmissionHistoryUrl("course-1", value)).toBeNull();
    }
  );
});
