import assert from "node:assert/strict";
import test from "node:test";

import { createReviewModeMiddleware } from "../lib/review_mode_middleware.mjs";


function createResponseRecorder() {
  return {
    body: undefined,
    statusCode: undefined,
    status(statusCode) {
      this.statusCode = statusCode;
      return this;
    },
    json(body) {
      this.body = body;
    },
  };
}


function runMiddleware(req, options = {}) {
  const res = createResponseRecorder();
  let nextCalled = false;
  const middleware = createReviewModeMiddleware({
    reviewTokenSecret: "secret",
    parseReviewTokenImpl: options.parseReviewTokenImpl ?? (() => options.payload ?? null),
    rolesAllowTeacherImpl: options.rolesAllowTeacherImpl ?? (() => true),
    sendJsonImpl: (response, statusCode, body) => {
      response.status(statusCode);
      response.json(body);
    },
  });

  middleware(req, res, () => {
    nextCalled = true;
  });

  return { res, nextCalled, req };
}


function reviewRequest(overrides = {}) {
  return {
    query: { review_mode: "true", contextId: "task-1" },
    path: "/contentUserData/1",
    method: "GET",
    user: { id: "teacher-1" },
    gustavMe: { roles: ["teacher"] },
    get(name) {
      return String(name).toLowerCase() === "cookie" ? "__Secure-gustav_h5p_review=token" : "";
    },
    ...overrides,
  };
}


test("review mode middleware ignores normal requests without an explicit review marker", () => {
  const req = {
    query: {},
    path: "/contentUserData/1",
    method: "GET",
    user: { id: "teacher-1" },
    gustavMe: { roles: ["teacher"] },
  };

  const result = runMiddleware(req);

  assert.equal(result.nextCalled, true);
  assert.deepEqual(result.req.user, { id: "teacher-1" });
});


test("review mode middleware lets the review model endpoint validate its bearer credential", () => {
  const req = {
    query: {},
    path: "/player/review",
    method: "GET",
    user: { id: "teacher-1" },
    gustavMe: { roles: ["teacher"] },
  };

  const result = runMiddleware(req, { parseReviewTokenImpl: () => null });

  assert.equal(result.nextCalled, true);
  assert.deepEqual(result.req.user, { id: "teacher-1" });
});


test("review mode middleware rejects non-teachers and invalid tokens", () => {
  const nonTeacher = runMiddleware(
    reviewRequest({
      user: { id: "student-1" },
      gustavMe: { roles: ["student"] },
    }),
    { rolesAllowTeacherImpl: () => false }
  );
  assert.equal(nonTeacher.nextCalled, false);
  assert.equal(nonTeacher.res.statusCode, 403);

  const invalidToken = runMiddleware(reviewRequest());
  assert.equal(invalidToken.nextCalled, false);
  assert.equal(invalidToken.res.statusCode, 403);

  const validPayload = {
      teacherSub: "teacher-1",
      studentSub: "student-1",
      contentId: "1",
      taskId: "task-1",
  };
  const missingCookie = runMiddleware(reviewRequest({ get: () => "" }), {
    parseReviewTokenImpl: (token) => token ? validPayload : null,
  });
  assert.equal(missingCookie.nextCalled, false);
  assert.equal(missingCookie.res.statusCode, 403);
});


test("review mode middleware rejects teacher, method, content and context mismatches", () => {
  const payload = {
    teacherSub: "teacher-1",
    studentSub: "student-1",
    contentId: "1",
    taskId: "task-1",
  };

  for (const req of [
    reviewRequest({
      user: { id: "teacher-2" },
    }),
    reviewRequest({
      method: "POST",
    }),
    reviewRequest({
      path: "/contentUserData/2",
    }),
    reviewRequest({
      query: { review_mode: "true", contextId: "other-task" },
    }),
  ]) {
    const result = runMiddleware(req, { payload });
    assert.equal(result.nextCalled, false);
    assert.equal(result.res.statusCode, 403);
  }
});


test("review mode middleware impersonates the reviewed student for valid user-data reads", () => {
  const req = reviewRequest();

  const result = runMiddleware(req, {
    payload: {
      teacherSub: "teacher-1",
      studentSub: "student-1",
      contentId: "1",
      taskId: "task-1",
    },
  });

  assert.equal(result.nextCalled, true);
  assert.deepEqual(result.req.user, {
    id: "student-1",
    name: "student-1",
    email: "student-1@local.invalid",
    type: "local",
  });
});
