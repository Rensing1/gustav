import assert from "node:assert/strict";
import test from "node:test";

import { buildFinishedSubmissionIdempotencyKey } from "../lib/finished_submission_context.mjs";


test("buildFinishedSubmissionIdempotencyKey is stable and Learning-compatible", () => {
  const first = buildFinishedSubmissionIdempotencyKey({
    userId: "student-1",
    courseId: "course-1",
    taskId: "task-1",
    contentId: "content-1",
    opened: 10,
    finished: 20,
    score: 3,
    maxScore: 4,
  });
  const second = buildFinishedSubmissionIdempotencyKey({
    userId: "student-1",
    courseId: "course-1",
    taskId: "task-1",
    contentId: "content-1",
    opened: 10,
    finished: 20,
    score: 3,
    maxScore: 4,
  });
  const changed = buildFinishedSubmissionIdempotencyKey({
    userId: "student-1",
    courseId: "course-1",
    taskId: "task-1",
    contentId: "content-1",
    opened: 10,
    finished: 20,
    score: 4,
    maxScore: 4,
  });

  assert.equal(first, second);
  assert.notEqual(first, changed);
  assert.match(first, /^h5pf_[a-f0-9]{56}$/);
  assert.ok(first.length <= 64);
});
