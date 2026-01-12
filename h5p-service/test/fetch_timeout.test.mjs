import assert from "node:assert/strict";
import test from "node:test";

import { fetchWithTimeout } from "../lib/fetch_timeout.mjs";


test("fetchWithTimeout: forwards a signal when timeout enabled", async () => {
  let seenSignal = null;
  const fakeFetch = async (_url, opts) => {
    seenSignal = opts?.signal || null;
    return { ok: true, status: 200 };
  };

  const res = await fetchWithTimeout("http://example.invalid", {}, { timeoutMs: 50, fetchImpl: fakeFetch });
  assert.equal(res.ok, true);
  assert.ok(seenSignal, "expected AbortSignal to be passed to fetch");
  assert.equal(typeof seenSignal.aborted, "boolean");
});


test("fetchWithTimeout: aborts and rejects on timeout", async () => {
  const fakeFetch = async (_url, opts) => {
    const signal = opts?.signal;
    assert.ok(signal, "expected AbortSignal");
    return await new Promise((_resolve, reject) => {
      signal.addEventListener(
        "abort",
        () => reject(signal.reason || new Error("aborted")),
        { once: true },
      );
    });
  };

  await assert.rejects(
    () => fetchWithTimeout("http://example.invalid", {}, { timeoutMs: 20, fetchImpl: fakeFetch }),
    (err) => String(err?.message || err).includes("fetch_timeout"),
  );
});

