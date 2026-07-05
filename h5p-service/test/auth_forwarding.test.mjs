import assert from "node:assert/strict";
import test from "node:test";

import {
  checkLearningH5PContentAccess,
  fetchGustavMe,
} from "../lib/auth_forwarding.mjs";


function jsonResponse(status, payload) {
  return {
    status,
    json: async () => payload,
  };
}


const options = {
  gustavWebInternalBase: "http://web:8000/",
  gustavFrontendInternalBase: "http://frontend:3000/",
  sessionCookieName: "gustav_session",
  frontendSessionCookieName: "gustav_bff_session",
  timeoutMs: 123,
};


test("fetchGustavMe authenticates through backend session cookies first", async () => {
  const calls = [];
  const result = await fetchGustavMe("other=1; gustav_session=legacy; gustav_bff_session=bff", {
    ...options,
    fetchWithTimeoutImpl: async (url, init, timeout) => {
      calls.push({ url, init, timeout });
      return jsonResponse(200, { sub: "student-1", roles: ["student"] });
    },
  });

  assert.deepEqual(result, { ok: true, payload: { sub: "student-1", roles: ["student"] } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://web:8000/api/me");
  assert.deepEqual(calls[0].init.headers, {
    "cache-control": "no-store",
    cookie: "gustav_session=legacy",
  });
  assert.deepEqual(calls[0].timeout, { timeoutMs: 123 });
});


test("fetchGustavMe falls back to the frontend BFF when backend session is unauthenticated", async () => {
  const calls = [];
  const result = await fetchGustavMe("gustav_session=expired; gustav_bff_session=bff", {
    ...options,
    fetchWithTimeoutImpl: async (url, init, timeout) => {
      calls.push({ url, init, timeout });
      if (url.endsWith("/api/me")) return jsonResponse(401, {});
      return jsonResponse(200, { sub: "student-bff", roles: ["student"] });
    },
  });

  assert.deepEqual(result, { ok: true, payload: { sub: "student-bff", roles: ["student"] } });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, "http://frontend:3000/internal/h5p/me");
  assert.deepEqual(calls[1].init.headers, {
    "cache-control": "no-store",
    cookie: "gustav_bff_session=bff",
  });
});


test("checkLearningH5PContentAccess encodes ids and accepts backend 204", async () => {
  const calls = [];
  const result = await checkLearningH5PContentAccess("course/id", "content id", "gustav_session=legacy", {
    ...options,
    fetchWithTimeoutImpl: async (url, init, timeout) => {
      calls.push({ url, init, timeout });
      return { status: 204 };
    },
  });

  assert.deepEqual(result, { ok: true, status: 204 });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://web:8000/api/learning/courses/course%2Fid/h5p/contents/content%20id/access");
  assert.deepEqual(calls[0].init.headers, {
    "cache-control": "no-store",
    cookie: "gustav_session=legacy",
  });
});


test("checkLearningH5PContentAccess falls back to BFF access checks after backend 401", async () => {
  const calls = [];
  const result = await checkLearningH5PContentAccess("course/id", "content id", "gustav_session=expired; gustav_bff_session=bff", {
    ...options,
    fetchWithTimeoutImpl: async (url, init) => {
      calls.push({ url, init });
      if (url.includes("/api/learning/")) return { status: 401 };
      return { status: 204 };
    },
  });

  assert.deepEqual(result, { ok: true, status: 204 });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, "http://frontend:3000/internal/h5p/access?course_id=course%2Fid&content_id=content%20id");
  assert.deepEqual(calls[1].init.headers, {
    "cache-control": "no-store",
    cookie: "gustav_bff_session=bff",
  });
});


test("checkLearningH5PContentAccess fails closed on upstream network errors", async () => {
  const result = await checkLearningH5PContentAccess("course", "content", "gustav_session=legacy", {
    ...options,
    fetchWithTimeoutImpl: async () => {
      throw new Error("network down");
    },
  });

  assert.deepEqual(result, { ok: false, status: 503 });
});
