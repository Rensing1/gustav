import assert from "node:assert/strict";
import test from "node:test";

import { CSP_DEBUG_HTML, CSP_DEFAULT } from "../lib/security_headers.mjs";
import { sendHtml, sendJson } from "../lib/response_helpers.mjs";


function createResponseRecorder() {
  const headers = {};
  return {
    body: undefined,
    headers,
    statusCode: undefined,
    typeValue: undefined,
    json(body) {
      this.body = body;
    },
    send(body) {
      this.body = body;
    },
    setHeader(name, value) {
      headers[name] = value;
    },
    status(statusCode) {
      this.statusCode = statusCode;
    },
    type(value) {
      this.typeValue = value;
      return this;
    },
  };
}


test("sendJson applies H5P security defaults, no-store caching and explicit headers", () => {
  const res = createResponseRecorder();

  sendJson(res, 403, { error: "forbidden" }, { Vary: "Origin" });

  assert.equal(res.statusCode, 403);
  assert.deepEqual(res.body, { error: "forbidden" });
  assert.equal(res.headers["Content-Security-Policy"], CSP_DEFAULT);
  assert.equal(res.headers["X-Content-Type-Options"], "nosniff");
  assert.equal(res.headers["Cache-Control"], "private, no-store");
  assert.equal(res.headers.Vary, "Origin");
});


test("sendHtml sends HTML responses with private cache headers and CSP overrides", () => {
  const res = createResponseRecorder();

  sendHtml(res, 200, "<h1>debug</h1>", { "Content-Security-Policy": CSP_DEBUG_HTML });

  assert.equal(res.statusCode, 200);
  assert.equal(res.typeValue, "html");
  assert.equal(res.body, "<h1>debug</h1>");
  assert.equal(res.headers["Content-Security-Policy"], CSP_DEBUG_HTML);
  assert.equal(res.headers["Cache-Control"], "private, no-store");
});
