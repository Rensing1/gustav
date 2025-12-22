/**
 * GUSTAV H5P Service (Phase-0 spike)
 *
 * Why:
 *   Provide a dedicated (future) H5P runtime under `/h5p/*` while keeping
 *   authentication based on the existing `gustav_session` cookie.
 *
 * Behavior:
 *   - `GET /healthz` returns a simple JSON liveness response (no auth).
 *   - `GET /auth/me` validates the session by forwarding the cookie to
 *     `GET <GUSTAV_WEB_INTERNAL_BASE>/api/me` and returns the same JSON payload.
 *   - All other routes are currently placeholders to validate proxy + auth wiring.
 *
 * Security notes:
 *   - "Fail closed": if auth cannot be proven, respond 401/403.
 *   - CSP is intentionally permissive for `/h5p` (per current decision),
 *     but still scoped to this service only (route-level separation via proxy).
 */

import http from "node:http";

const port = Number.parseInt(process.env.PORT || "3000", 10);
const gustavWebInternalBase = process.env.GUSTAV_WEB_INTERNAL_BASE || "http://web:8000";
const sessionCookieName = process.env.SESSION_COOKIE_NAME || "gustav_session";
const authCacheTtlSeconds = Number.parseInt(process.env.AUTH_CACHE_TTL_SECONDS || "30", 10);

/**
 * Cache auth lookups for short bursts (editor/player loads many assets quickly).
 * Key: session id. Value: { expiresAtMs, payload }
 */
const authCache = new Map();

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  // Intentionally permissive CSP for `/h5p` (same-origin H5P requires JS).
  // Tightening requires a content-type whitelist and real-world CSP testing.
  "Content-Security-Policy":
    "default-src * data: blob:; " +
    "script-src * 'unsafe-inline' 'unsafe-eval' data: blob:; " +
    "style-src * 'unsafe-inline' data: blob:; " +
    "img-src * data: blob:; " +
    "connect-src *; " +
    "frame-src *; " +
    "font-src * data: blob:;",
};

function sendJson(res, statusCode, body) {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    ...SECURITY_HEADERS,
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

function sendHtml(res, statusCode, html) {
  res.writeHead(statusCode, {
    ...SECURITY_HEADERS,
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": Buffer.byteLength(html),
  });
  res.end(html);
}

function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(";")) {
    const [rawKey, ...rawRest] = part.trim().split("=");
    if (!rawKey) continue;
    out[rawKey] = decodeURIComponent(rawRest.join("="));
  }
  return out;
}

function rolesAllowTeacher(roles) {
  if (!Array.isArray(roles)) return false;
  return roles.includes("admin") || roles.includes("teacher");
}

function rolesAllowStudentOrTeacher(roles) {
  if (!Array.isArray(roles)) return false;
  return roles.includes("admin") || roles.includes("teacher") || roles.includes("student");
}

async function fetchGustavMe(cookieHeader) {
  const url = `${gustavWebInternalBase.replace(/\\/$/, "")}/api/me`;
  const r = await fetch(url, {
    method: "GET",
    headers: {
      cookie: cookieHeader,
      // Mirror "no-store" semantics of /api/me; avoid accidental caches.
      "cache-control": "no-store",
    },
  });
  if (r.status !== 200) {
    return { ok: false, status: r.status };
  }
  const payload = await r.json();
  return { ok: true, payload };
}

async function requireAuth(req, res) {
  const cookieHeader = req.headers.cookie || "";
  const cookies = parseCookies(cookieHeader);
  const sid = cookies[sessionCookieName];
  if (!sid) {
    sendJson(res, 401, { error: "unauthenticated" });
    return null;
  }

  const cached = authCache.get(sid);
  const now = Date.now();
  if (cached && cached.expiresAtMs > now) {
    return cached.payload;
  }

  try {
    const me = await fetchGustavMe(cookieHeader);
    if (!me.ok) {
      sendJson(res, me.status === 401 ? 401 : 502, { error: "unauthenticated" });
      return null;
    }
    authCache.set(sid, { expiresAtMs: now + authCacheTtlSeconds * 1000, payload: me.payload });
    return me.payload;
  } catch {
    sendJson(res, 502, { error: "upstream_unavailable" });
    return null;
  }
}

const server = http.createServer(async (req, res) => {
  const method = req.method || "GET";
  const url = new URL(req.url || "/", "http://localhost");
  const path = url.pathname;

  if (method === "GET" && path === "/healthz") {
    sendJson(res, 200, { status: "healthy", service: "gustav-h5p", time: new Date().toISOString() });
    return;
  }

  if (method === "GET" && path === "/auth/me") {
    const me = await requireAuth(req, res);
    if (!me) return;
    sendJson(res, 200, me);
    return;
  }

  if (method === "GET" && path === "/editor") {
    const me = await requireAuth(req, res);
    if (!me) return;
    if (!rolesAllowTeacher(me.roles)) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    sendHtml(
      res,
      200,
      [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\" />",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        "<title>H5P Editor (placeholder)</title>",
        "</head><body>",
        "<h1>H5P Editor (Phase-0 placeholder)</h1>",
        "<p>Auth wiring OK. Next: mount Lumi editor here.</p>",
        "</body></html>",
      ].join(""),
    );
    return;
  }

  if (method === "GET" && path === "/player") {
    const me = await requireAuth(req, res);
    if (!me) return;
    if (!rolesAllowStudentOrTeacher(me.roles)) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    sendHtml(
      res,
      200,
      [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\" />",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        "<title>H5P Player (placeholder)</title>",
        "</head><body>",
        "<h1>H5P Player (Phase-0 placeholder)</h1>",
        "<p>Auth wiring OK. Next: mount Lumi player here.</p>",
        "</body></html>",
      ].join(""),
    );
    return;
  }

  sendJson(res, 404, { error: "not_found" });
});

server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`gustav-h5p listening on :${port} (web=${gustavWebInternalBase})`);
});

