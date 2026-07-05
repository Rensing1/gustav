import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import { parseReviewToken } from "../lib/review_tokens.mjs";


function signReviewPayload(payload, secret) {
  const payloadBytes = Buffer.from(JSON.stringify(payload), "utf-8");
  const payloadB64 = payloadBytes.toString("base64url");
  const sigB64 = createHmac("sha256", secret).update(payloadBytes).digest("base64url");
  return `${payloadB64}.${sigB64}`;
}


test("parseReviewToken accepts a valid signed review token", () => {
  const token = signReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      course_id: "course-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 200,
    },
    "secret",
  );

  assert.deepEqual(parseReviewToken(token, { secret: "secret", nowSeconds: 100 }), {
    teacherSub: "teacher-1",
    studentSub: "student-1",
    courseId: "course-1",
    taskId: "task-1",
    contentId: "content-1",
    exp: 200,
  });
});


test("parseReviewToken rejects expired and unsigned tokens", () => {
  const expired = signReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      course_id: "course-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 99,
    },
    "secret",
  );

  assert.equal(parseReviewToken(expired, { secret: "secret", nowSeconds: 100 }), null);
  assert.equal(parseReviewToken(expired, { secret: "", nowSeconds: 100 }), null);
  assert.equal(parseReviewToken("not-a-token", { secret: "secret", nowSeconds: 100 }), null);
});


test("parseReviewToken rejects tampered signatures and incomplete payloads", () => {
  const valid = signReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      course_id: "course-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 200,
    },
    "secret",
  );
  const tampered = `${valid.split(".")[0]}.${signReviewPayload({ other: true }, "other-secret").split(".")[1]}`;
  const incomplete = signReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      course_id: "course-1",
      task_id: "task-1",
      exp: 200,
    },
    "secret",
  );

  assert.equal(parseReviewToken(tampered, { secret: "secret", nowSeconds: 100 }), null);
  assert.equal(parseReviewToken(incomplete, { secret: "secret", nowSeconds: 100 }), null);
});
