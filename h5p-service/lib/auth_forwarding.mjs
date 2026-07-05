import { buildSessionCookieHeader } from "./cookies.mjs";
import { fetchWithTimeout } from "./fetch_timeout.mjs";


function trimBaseUrl(value) {
  return String(value || "").replace(/\/+$/, "");
}


function forwardingOptions(options = {}) {
  return {
    gustavWebInternalBase: trimBaseUrl(options.gustavWebInternalBase),
    gustavFrontendInternalBase: trimBaseUrl(options.gustavFrontendInternalBase),
    sessionCookieName: options.sessionCookieName || "gustav_session",
    frontendSessionCookieName: options.frontendSessionCookieName || "gustav_bff_session",
    timeoutMs: options.timeoutMs,
    fetchWithTimeoutImpl: options.fetchWithTimeoutImpl || fetchWithTimeout,
  };
}


export async function fetchGustavMe(cookieHeader, options = {}) {
  const config = forwardingOptions(options);
  const backendUrl = `${config.gustavWebInternalBase}/api/me`;
  const frontendUrl = `${config.gustavFrontendInternalBase}/internal/h5p/me`;
  const sessionCookieHeader = buildSessionCookieHeader(cookieHeader, config.sessionCookieName);
  const frontendCookieHeader = buildSessionCookieHeader(cookieHeader, config.frontendSessionCookieName);

  const backendHeaders = {
    "cache-control": "no-store",
  };
  if (sessionCookieHeader) backendHeaders.cookie = sessionCookieHeader;

  if (sessionCookieHeader) {
    const response = await config.fetchWithTimeoutImpl(
      backendUrl,
      { method: "GET", headers: backendHeaders },
      { timeoutMs: config.timeoutMs },
    );
    if (response.status === 200) {
      const payload = await response.json();
      return { ok: true, payload };
    }
    if (!frontendCookieHeader || response.status !== 401) {
      return { ok: false, status: response.status };
    }
  }

  if (!frontendCookieHeader) {
    return { ok: false, status: 401 };
  }

  const frontendHeaders = {
    "cache-control": "no-store",
    cookie: frontendCookieHeader,
  };
  const response = await config.fetchWithTimeoutImpl(
    frontendUrl,
    { method: "GET", headers: frontendHeaders },
    { timeoutMs: config.timeoutMs },
  );
  if (response.status !== 200) {
    return { ok: false, status: response.status };
  }
  const payload = await response.json();
  return { ok: true, payload };
}


export async function checkLearningH5PContentAccess(courseId, contentId, cookieHeader, options = {}) {
  const config = forwardingOptions(options);
  const backendUrl =
    `${config.gustavWebInternalBase}/api/learning/courses/${encodeURIComponent(courseId)}` +
    `/h5p/contents/${encodeURIComponent(contentId)}/access`;
  const frontendUrl =
    `${config.gustavFrontendInternalBase}/internal/h5p/access` +
    `?course_id=${encodeURIComponent(courseId)}&content_id=${encodeURIComponent(contentId)}`;
  const sessionCookieHeader = buildSessionCookieHeader(cookieHeader, config.sessionCookieName);
  const frontendCookieHeader = buildSessionCookieHeader(cookieHeader, config.frontendSessionCookieName);
  const headers = {
    "cache-control": "no-store",
  };
  if (sessionCookieHeader) headers.cookie = sessionCookieHeader;

  try {
    if (sessionCookieHeader) {
      const response = await config.fetchWithTimeoutImpl(
        backendUrl,
        { method: "GET", headers },
        { timeoutMs: config.timeoutMs },
      );
      if (response.status === 204) {
        return { ok: true, status: 204 };
      }
      if (!frontendCookieHeader || response.status !== 401) {
        return { ok: false, status: response.status };
      }
    }

    if (!frontendCookieHeader) {
      return { ok: false, status: 401 };
    }

    const frontendHeaders = {
      "cache-control": "no-store",
      cookie: frontendCookieHeader,
    };
    const response = await config.fetchWithTimeoutImpl(
      frontendUrl,
      { method: "GET", headers: frontendHeaders },
      { timeoutMs: config.timeoutMs },
    );
    if (response.status === 204) {
      return { ok: true, status: 204 };
    }
    return { ok: false, status: response.status };
  } catch {
    // Upstream network errors: callers fail closed.
    return { ok: false, status: 503 };
  }
}
