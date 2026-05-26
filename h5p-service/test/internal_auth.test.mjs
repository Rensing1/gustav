import assert from "node:assert/strict";
import test from "node:test";

import {
  authenticateInternalTeacher,
  isInternalAuth,
  rolesAllowTeacher,
} from "../lib/internal_auth.mjs";

function makeRequest(headers) {
  const normalized = Object.fromEntries(
    Object.entries(headers || {}).map(([key, value]) => [key.toLowerCase(), String(value)]),
  );
  return {
    get(name) {
      return normalized[String(name).toLowerCase()] || "";
    },
  };
}

test("authenticateInternalTeacher: rejects missing or wrong shared secrets", () => {
  const missing = makeRequest({});
  const wrong = makeRequest({
    "x-gustav-h5p-internal-secret": "wrong",
    "x-gustav-user-sub": "teacher-1",
    "x-gustav-user-roles": "teacher",
  });

  assert.equal(authenticateInternalTeacher(missing, "shared-secret"), false);
  assert.equal(authenticateInternalTeacher(wrong, "shared-secret"), false);
  assert.equal(isInternalAuth(missing), false);
  assert.equal(isInternalAuth(wrong), false);
  assert.equal(missing.gustavMe, undefined);
  assert.equal(wrong.gustavMe, undefined);
});

test("authenticateInternalTeacher: sets sanitized internal teacher context", () => {
  const req = makeRequest({
    "x-gustav-h5p-internal-secret": "shared-secret",
    "x-gustav-user-sub": "teacher\r\n-1",
    "x-gustav-user-name": "CLI\r\nTeacher",
    "x-gustav-user-roles": "teacher, admin",
  });

  assert.equal(authenticateInternalTeacher(req, "shared-secret"), true);
  assert.equal(isInternalAuth(req), true);
  assert.deepEqual(req.gustavMe, {
    sub: "teacher-1",
    name: "CLITeacher",
    roles: ["teacher", "admin"],
  });
  assert.deepEqual(req.user, {
    id: "teacher-1",
    name: "CLITeacher",
    email: "teacher-1@local.invalid",
    type: "local",
  });
  assert.equal(req.language, "en");
});

test("rolesAllowTeacher: internal auth still requires teacher or admin role", () => {
  assert.equal(rolesAllowTeacher(["teacher"]), true);
  assert.equal(rolesAllowTeacher(["admin"]), true);
  assert.equal(rolesAllowTeacher(["student"]), false);
  assert.equal(rolesAllowTeacher([]), false);
  assert.equal(rolesAllowTeacher(undefined), false);
});
