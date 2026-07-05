import assert from "node:assert/strict";
import test from "node:test";

import { buildFinishedSubmissionIdempotencyKey, parseOriginForForwarding } from "../lib/finished_submission_context.mjs";


function requestWithHeaders(headers) {
  const normalized = new Map(Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]));
  return {
    get(name) {
      return normalized.get(String(name || "").toLowerCase()) || "";
    },
  };
}


test("parseOriginForForwarding prefers Origin and normalizes forwarded fields", () => {
  const out = parseOriginForForwarding(requestWithHeaders({ origin: "https://app.example:8443" }));

  assert.deepEqual(out, {
    origin: "https://app.example:8443",
    scheme: "https",
    host: "app.example",
    port: "8443",
  });
});


test("parseOriginForForwarding falls back to same browser Referer origin", () => {
  const out = parseOriginForForwarding(
    requestWithHeaders({ origin: "null", referer: "http://app.localhost:4011/learning/path?x=1" }),
  );

  assert.deepEqual(out, {
    origin: "http://app.localhost:4011",
    scheme: "http",
    host: "app.localhost",
    port: "4011",
  });
});


test("parseOriginForForwarding returns null when no valid browser origin exists", () => {
  assert.equal(parseOriginForForwarding(requestWithHeaders({})), null);
  assert.equal(parseOriginForForwarding(requestWithHeaders({ origin: "not a url" })), null);
});


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
