import assert from "node:assert/strict";
import test from "node:test";

import { applySecurityHeaders, CSP_DEBUG_HTML, CSP_DEFAULT, SECURITY_HEADERS } from "../lib/security_headers.mjs";


test("CSP_DEFAULT keeps H5P responses strict without wildcard or unsafe-eval", () => {
  assert.match(CSP_DEFAULT, /default-src 'self'/);
  assert.match(CSP_DEFAULT, /script-src 'self'/);
  assert.doesNotMatch(CSP_DEFAULT, /\*/);
  assert.doesNotMatch(CSP_DEFAULT, /unsafe-eval/);
});


test("CSP_DEBUG_HTML is scoped to standalone debug pages with inline scripts", () => {
  assert.match(CSP_DEBUG_HTML, /script-src 'self' 'unsafe-inline'/);
  assert.match(CSP_DEBUG_HTML, /style-src 'self' 'unsafe-inline'/);
  assert.doesNotMatch(CSP_DEBUG_HTML, /unsafe-eval/);
});


test("applySecurityHeaders sets defaults and preserves explicit overrides", () => {
  const headers = {};
  const res = {
    setHeader(name, value) {
      headers[name] = value;
    },
  };

  applySecurityHeaders(res, { "Content-Security-Policy": CSP_DEBUG_HTML, Vary: "Origin" });

  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");
  assert.equal(headers["Content-Security-Policy"], CSP_DEBUG_HTML);
  assert.equal(headers.Vary, "Origin");
  assert.equal(SECURITY_HEADERS["Content-Security-Policy"], CSP_DEFAULT);
});
