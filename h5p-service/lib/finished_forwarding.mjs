/**
 * finishedData → Learning submission forwarding (best-effort).
 *
 * Why:
 *   GUSTAV's Teacher dashboards read H5P progress from `learning_submissions`.
 *   The H5P runtime reports "finished" runs to the sidecar (`POST /finishedData`),
 *   and the sidecar forwards a minimal, idempotent submission to the Learning API.
 *
 * Design:
 *   - Best-effort: the student should not be blocked if the Learning API is down.
 *   - Bounded retry: small retry loop for transient 5xx/network failures.
 *   - Metrics: in-memory counters (no PII) to improve failure visibility in logs/ops.
 *
 * Security:
 *   - Never log request payloads or user identifiers here.
 *   - Do not read or log upstream response bodies (defense-in-depth).
 */

import { fetchWithTimeout } from "./fetch_timeout.mjs";


export function createFinishedForwardingMetrics() {
  return {
    attemptsTotal: 0,
    retryTotal: 0,
    successTotal: 0,
    failureTotal: 0,
  };
}


function _sleep(ms, sleepImpl) {
  const msInt = Number.isFinite(ms) ? Math.max(0, Math.trunc(ms)) : 0;
  const impl = sleepImpl || ((t) => new Promise((resolve) => setTimeout(resolve, t)));
  return impl(msInt);
}


function _errorCode(err) {
  const msg = String(err?.message || err || "");
  if (msg.includes("fetch_timeout")) return "fetch_timeout";
  return "fetch_failed";
}


export async function forwardLearningSubmission({
  url,
  headers,
  body,
  timeoutMs,
  maxAttempts = 2,
  baseBackoffMs = 50,
  fetchImpl,
  sleepImpl,
  metrics,
} = {}) {
  const attempts = Math.max(1, Math.trunc(Number(maxAttempts) || 1));

  for (let attemptNr = 1; attemptNr <= attempts; attemptNr += 1) {
    if (metrics) metrics.attemptsTotal += 1;

    try {
      const res = await fetchWithTimeout(
        url,
        { method: "POST", headers, body },
        { timeoutMs, fetchImpl },
      );

      if (res.ok) {
        if (metrics) metrics.successTotal += 1;
        return { ok: true, status: res.status, attempts: attemptNr };
      }

      const retryable = res.status >= 500;
      const canRetry = attemptNr < attempts && retryable;
      if (canRetry) {
        if (metrics) metrics.retryTotal += 1;
        await _sleep(baseBackoffMs, sleepImpl);
        continue;
      }

      if (metrics) metrics.failureTotal += 1;
      return { ok: false, status: res.status, attempts: attemptNr, error: "upstream_status" };
    } catch (err) {
      const canRetry = attemptNr < attempts;
      if (canRetry) {
        if (metrics) metrics.retryTotal += 1;
        await _sleep(baseBackoffMs, sleepImpl);
        continue;
      }

      if (metrics) metrics.failureTotal += 1;
      return { ok: false, status: null, attempts: attemptNr, error: _errorCode(err) };
    }
  }

  // Unreachable (the loop returns on the final attempt), but keep a safe fallback.
  if (metrics) metrics.failureTotal += 1;
  return { ok: false, status: null, attempts: attempts, error: "unexpected" };
}

