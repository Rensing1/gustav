import assert from "node:assert/strict";
import { createCipheriv, createHash } from "node:crypto";
import test from "node:test";

import {
  parseReviewToken,
  reviewCookieName,
  reviewHandleFromToken,
  reviewTokenFromAuthorizationHeader,
} from "../lib/review_tokens.mjs";


function encryptReviewPayload(payload, secret, nonce = Buffer.alloc(12, 7)) {
  const payloadBytes = Buffer.from(JSON.stringify(payload), "utf-8");
  const key = createHash("sha256").update(secret, "utf-8").digest();
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  cipher.setAAD(Buffer.from("gustav-h5p-review-v1", "utf-8"));
  const ciphertext = Buffer.concat([cipher.update(payloadBytes), cipher.final(), cipher.getAuthTag()]);
  return `v1.${nonce.toString("base64url")}.${ciphertext.toString("base64url")}`;
}


test("parseReviewToken accepts a valid encrypted review credential", () => {
  const token = encryptReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 200,
    },
    "secret",
  );

  assert.deepEqual(parseReviewToken(token, { secret: "secret", nowSeconds: 100 }), {
    teacherSub: "teacher-1",
    studentSub: "student-1",
    taskId: "task-1",
    contentId: "content-1",
    exp: 200,
  });
});


test("parseReviewToken accepts a credential issued by the Python Teaching adapter", () => {
  const pythonIssued = "v1.AAECAwQFBgcICQoL.0vTH5Ae3AO-1Cxf7JGZnXgQUiPqWj5g9pZHZoTRT8Jjp5NfcFMxHt8zJ0zoDwH-MAZHPGPmhU2r2O6W-TaCD5yAFFz0hAqHDWfXm5aeQheioWP2N38NsnI9br9F3Qblzs6OKCAqs8ijzlcQh1SU_TRLTGNbja1t-ahEP";

  assert.deepEqual(parseReviewToken(pythonIssued, { secret: "secret", nowSeconds: 100 }), {
    teacherSub: "teacher-1",
    studentSub: "student-1",
    taskId: "task-1",
    contentId: "content-1",
    exp: 700,
  });
});


test("parseReviewToken rejects expired and unsigned tokens", () => {
  const expired = encryptReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
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


test("parseReviewToken rejects tampered ciphertext and incomplete payloads", () => {
  const valid = encryptReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 200,
    },
    "secret",
  );
  const [version, nonce, ciphertext] = valid.split(".");
  const tamperedBytes = Buffer.from(ciphertext, "base64url");
  tamperedBytes[0] ^= 1;
  const tampered = `${version}.${nonce}.${tamperedBytes.toString("base64url")}`;
  const incomplete = encryptReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      task_id: "task-1",
      exp: 200,
    },
    "secret",
  );

  assert.equal(parseReviewToken(tampered, { secret: "secret", nowSeconds: 100 }), null);
  assert.equal(parseReviewToken(incomplete, { secret: "secret", nowSeconds: 100 }), null);
});


test("reviewTokenFromAuthorizationHeader accepts only a non-empty Bearer credential", () => {
  assert.equal(reviewTokenFromAuthorizationHeader("Bearer encrypted-token"), "encrypted-token");
  assert.equal(reviewTokenFromAuthorizationHeader("bearer encrypted-token"), "encrypted-token");
  assert.equal(reviewTokenFromAuthorizationHeader("Basic encrypted-token"), null);
  assert.equal(reviewTokenFromAuthorizationHeader("Bearer"), null);
  assert.equal(reviewTokenFromAuthorizationHeader(""), null);
});


test("review handles derive from the random nonce and create isolated secure cookie names", () => {
  const token = encryptReviewPayload(
    {
      teacher_sub: "teacher-1",
      student_sub: "student-1",
      task_id: "task-1",
      content_id: "content-1",
      exp: 200,
    },
    "secret",
    Buffer.alloc(12, 9),
  );
  const expectedHandle = Buffer.alloc(12, 9).toString("base64url");

  assert.equal(reviewHandleFromToken(token), expectedHandle);
  assert.equal(
    reviewCookieName(expectedHandle),
    `__Secure-gustav_h5p_review_${expectedHandle}`,
  );
  assert.equal(reviewHandleFromToken("not-a-token"), null);
  assert.equal(reviewCookieName("../invalid"), null);
  assert.equal(reviewCookieName(""), null);
});
