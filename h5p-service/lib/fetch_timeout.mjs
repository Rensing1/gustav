/**
 * Fetch helper with a hard timeout (AbortController).
 *
 * Why:
 *   The H5P sidecar calls back into the main GUSTAV web service (`/api/me`,
 *   Learning access-check, finishedData → submission). Unbounded `fetch()` calls
 *   can hang forever on network/proxy failures and tie up the Node event loop.
 *
 * KISS:
 *   - Provide a single helper used by all upstream calls.
 *   - Keep behavior deterministic and easy to unit test.
 *
 * Security:
 *   - Upstream calls are treated as "fail closed" by their callers.
 */

export async function fetchWithTimeout(url, options = {}, { timeoutMs, fetchImpl } = {}) {
  const ms = Number.isFinite(timeoutMs) ? Math.trunc(timeoutMs) : 0;
  const doTimeout = ms > 0;
  const impl = fetchImpl || fetch;

  // Combine an existing AbortSignal with our timeout AbortController.
  const originalSignal = options?.signal;
  const controller = doTimeout ? new AbortController() : null;
  const signal = controller ? controller.signal : originalSignal;

  if (controller && originalSignal) {
    try {
      if (originalSignal.aborted) {
        controller.abort(originalSignal.reason);
      } else {
        originalSignal.addEventListener(
          "abort",
          () => {
            try {
              controller.abort(originalSignal.reason);
            } catch {
              controller.abort();
            }
          },
          { once: true },
        );
      }
    } catch {
      // If the signal cannot be observed, we still keep the timeout guard.
    }
  }

  let timer = null;
  if (controller) {
    timer = setTimeout(() => {
      try {
        controller.abort(new Error("fetch_timeout"));
      } catch {
        controller.abort();
      }
    }, ms);
  }

  try {
    return await impl(url, { ...(options || {}), ...(controller ? { signal } : {}) });
  } finally {
    if (timer) clearTimeout(timer);
  }
}

