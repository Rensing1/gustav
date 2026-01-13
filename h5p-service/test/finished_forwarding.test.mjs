import assert from "node:assert/strict";
import test from "node:test";

import { createFinishedForwardingMetrics, forwardLearningSubmission } from "../lib/finished_forwarding.mjs";


test("forwardLearningSubmission: retries once on 5xx and records metrics", async () => {
  const callLog = [];
  const fakeFetch = async (_url, _opts) => {
    callLog.push("call");
    if (callLog.length === 1) return { ok: false, status: 503 };
    return { ok: true, status: 204 };
  };

  const sleptMs = [];
  const fakeSleep = async (ms) => {
    sleptMs.push(ms);
  };

  const metrics = createFinishedForwardingMetrics();
  const result = await forwardLearningSubmission({
    url: "http://example.invalid/api/learning/submissions",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "h5p", score_raw: 1, score_max: 2 }),
    timeoutMs: 50,
    maxAttempts: 2,
    baseBackoffMs: 25,
    fetchImpl: fakeFetch,
    sleepImpl: fakeSleep,
    metrics,
  });

  assert.equal(result.ok, true);
  assert.equal(result.status, 204);
  assert.equal(result.attempts, 2);
  assert.deepEqual(sleptMs, [25]);
  assert.equal(metrics.attemptsTotal, 2);
  assert.equal(metrics.retryTotal, 1);
  assert.equal(metrics.successTotal, 1);
  assert.equal(metrics.failureTotal, 0);
});


test("forwardLearningSubmission: does not retry on 4xx and records failure", async () => {
  const callLog = [];
  const fakeFetch = async (_url, _opts) => {
    callLog.push("call");
    return { ok: false, status: 400 };
  };

  const metrics = createFinishedForwardingMetrics();
  const result = await forwardLearningSubmission({
    url: "http://example.invalid/api/learning/submissions",
    headers: { "content-type": "application/json" },
    body: "{}",
    timeoutMs: 50,
    maxAttempts: 3,
    baseBackoffMs: 25,
    fetchImpl: fakeFetch,
    sleepImpl: async () => {},
    metrics,
  });

  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.equal(result.attempts, 1);
  assert.equal(callLog.length, 1);
  assert.equal(metrics.attemptsTotal, 1);
  assert.equal(metrics.retryTotal, 0);
  assert.equal(metrics.successTotal, 0);
  assert.equal(metrics.failureTotal, 1);
});

