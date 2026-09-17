import { buildSessionCookieHeader } from "./cookies.mjs";
import { fetchWithTimeout } from "./fetch_timeout.mjs";

async function backendRead(path, cookieHeader, options, expected) {
  const cookie = buildSessionCookieHeader(cookieHeader, options.sessionCookieName || "gustav_session");
  if (!cookie) return { ok: false, status: 401 };
  try {
    const response = await (options.fetchWithTimeoutImpl || fetchWithTimeout)(
      `${String(options.gustavWebInternalBase || "").replace(/\/+$/, "")}${path}`,
      { method: "GET", headers: { "cache-control": "no-store", cookie } },
      { timeoutMs: options.timeoutMs },
    );
    if (response.status !== expected) return { ok: false, status: response.status };
    return expected === 200 ? { ok: true, payload: await response.json() } : { ok: true, status: expected };
  } catch {
    return { ok: false, status: 503 };
  }
}

export function fetchGustavMe(cookieHeader, options = {}) {
  return backendRead('/api/me', cookieHeader, options, 200);
}

export function checkLearningH5PContentAccess(courseId, contentId, cookieHeader, options = {}) {
  return backendRead(`/api/learning/courses/${encodeURIComponent(courseId)}/h5p/contents/${encodeURIComponent(contentId)}/access`, cookieHeader, options, 204);
}
