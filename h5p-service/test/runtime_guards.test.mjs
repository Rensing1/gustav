import assert from "node:assert/strict";
import test from "node:test";

import {
  getPublicOrigin,
  parseMaxEntries,
  pruneCacheToMaxEntries,
} from "../lib/runtime_guards.mjs";


function reqWithHeaders(headers) {
  return {
    get(name) {
      return headers[String(name).toLowerCase()];
    },
    protocol: "http",
  };
}


test("parseMaxEntries falls back for invalid or negative values", () => {
  assert.equal(parseMaxEntries("25", 10), 25);
  assert.equal(parseMaxEntries("", 10), 10);
  assert.equal(parseMaxEntries("-1", 10), 10);
  assert.equal(parseMaxEntries("not-a-number", 10), 10);
});


test("pruneCacheToMaxEntries sweeps expired entries and applies max size", () => {
  const cache = new Map([
    ["expired", { expiresAtMs: 99 }],
    ["oldest", { expiresAtMs: 200 }],
    ["newest", { expiresAtMs: 300 }],
  ]);

  pruneCacheToMaxEntries(cache, 100, 1);

  assert.deepEqual([...cache.keys()], ["newest"]);
});


test("getPublicOrigin normalizes forwarded host and forwarded port", () => {
  const req = reqWithHeaders({
    "x-forwarded-proto": "https",
    "x-forwarded-host": "app.localhost",
    "x-forwarded-port": "8443",
  });

  assert.equal(getPublicOrigin(req), "https://app.localhost:8443");
});


test("getPublicOrigin omits default ports", () => {
  const req = reqWithHeaders({
    "x-forwarded-proto": "https",
    "x-forwarded-host": "app.localhost",
    "x-forwarded-port": "443",
  });

  assert.equal(getPublicOrigin(req), "https://app.localhost");
});
