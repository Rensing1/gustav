import { fetchGustavMe } from "./auth_forwarding.mjs";
import { parseCookies } from "./cookies.mjs";
import {
  authenticateInternalTeacher,
  isInternalAuth,
  rolesAllowAdmin,
  rolesAllowStudentOrTeacher,
  rolesAllowTeacher,
} from "./internal_auth.mjs";
import { sendJson } from "./response_helpers.mjs";


export function parseMaxEntries(raw, defaultValue) {
  const n = Number.parseInt(String(raw || "").trim(), 10);
  if (!Number.isFinite(n) || n < 0) return defaultValue;
  return n;
}


export function pruneCacheToMaxEntries(cache, nowMs, maxEntries) {
  // TTL sweep first (keeps memory stable without requiring access per key).
  for (const [k, v] of cache.entries()) {
    const expiresAtMs = v?.expiresAtMs;
    if (typeof expiresAtMs !== "number" || expiresAtMs <= nowMs) cache.delete(k);
  }

  // Size cap (oldest-first, approximates LRU when callers "touch" hot keys).
  while (cache.size > maxEntries) {
    const firstKey = cache.keys().next().value;
    if (firstKey === undefined) break;
    cache.delete(firstKey);
  }
}


export function getPublicOrigin(req) {
  const proto = String(req.get("x-forwarded-proto") || req.protocol || "")
    .split(",")[0]
    .trim()
    .toLowerCase();
  const xfHost = String(req.get("x-forwarded-host") || req.get("host") || "")
    .split(",")[0]
    .trim();
  if (!proto || !xfHost) return null;

  // Some proxy setups strip the port from `X-Forwarded-Host`, but set
  // `X-Forwarded-Port` instead. We normalize this so CSRF same-origin checks
  // behave like browsers: default ports are omitted from origins.
  const xfPort = String(req.get("x-forwarded-port") || "").split(",")[0].trim();

  let hostname = "";
  let port = "";
  try {
    const u = new URL(`${proto}://${xfHost}`);
    hostname = String(u.hostname || "").toLowerCase();
    port = String(u.port || "");
  } catch {
    return null;
  }
  if (!hostname) return null;
  if (xfPort) port = xfPort;

  const defaultPort = proto === "https" ? "443" : "80";
  const includePort = port && port !== defaultPort;
  const hostPart = hostname.includes(":") ? `[${hostname}]` : hostname;
  return `${proto}://${includePort ? `${hostPart}:${port}` : hostPart}`;
}


export function requireSameOrigin(req, res, next) {
  if (isInternalAuth(req)) {
    next();
    return;
  }
  const expected = getPublicOrigin(req);
  const origin = String(req.get("origin") || "");
  const referer = String(req.get("referer") || "");

  if (!expected) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  const originMatches = origin ? origin === expected : false;
  let refererMatches = false;
  if (referer) {
    try {
      const parsed = new URL(referer);
      refererMatches = `${parsed.protocol}//${parsed.host}` === expected;
    } catch {
      refererMatches = false;
    }
  }

  // Require at least one same-origin indicator for browser write requests.
  if (!origin && !referer) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }
  // Fast-path: valid, non-null Origin header matches expected.
  if (originMatches) {
    next();
    return;
  }

  // Fail closed when a non-null Origin is present but mismatching.
  // (Browsers should not send a mismatching Origin for same-origin requests.)
  if (origin) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  // Fallback: accept same-origin Referer only when Origin is absent.
  if (!refererMatches) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  next();
}


export function createRequireAuth({
  h5pInternalSharedSecret,
  sessionCookieName,
  authForwardingOptions,
}) {
  return async function requireAuth(req, res, next) {
    if (authenticateInternalTeacher(req, h5pInternalSharedSecret)) {
      next();
      return;
    }

    const cookieHeader = req.get("cookie") || "";
    const cookies = parseCookies(cookieHeader);
    const sessionId = cookies[sessionCookieName];
    const sessionKey = sessionId;
    if (!sessionKey) {
      sendJson(res, 401, { error: "unauthenticated" });
      return;
    }

    try {
      const me = await fetchGustavMe(cookieHeader, authForwardingOptions);
      if (!me.ok) {
        if (me.status === 401) {
          sendJson(res, 401, { error: "unauthenticated" });
          return;
        }
        sendJson(res, 503, { error: "auth_unavailable" });
        return;
      }
      req.gustavMe = me.payload;
      req.user = {
        id: me.payload.sub,
        name: me.payload.name || me.payload.sub,
        email: `${me.payload.sub}@local.invalid`,
        type: "local",
      };
      req.language = "de";
      next();
      return;
    } catch {
      sendJson(res, 503, { error: "auth_unavailable" });
      return;
    }
  };
}


export function requireStudentOrTeacher(req, res, next) {
  if (!rolesAllowStudentOrTeacher(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}


export function requireTeacher(req, res, next) {
  if (!rolesAllowTeacher(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}


export function requireAdmin(req, res, next) {
  if (!rolesAllowAdmin(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}
