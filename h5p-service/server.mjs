/**
 * GUSTAV H5P Service (Phase 1 – Lumi PoC)
 *
 * Why:
 *   Provide a dedicated H5P runtime under `/h5p/*` while supporting both the
 *   legacy backend session cookie and the new SvelteKit Browser-BFF session.
 *
 * Behavior:
 *   - This service is reverse-proxied under `/h5p/*` on `app.localhost`.
 *   - Caddy uses `handle_path /h5p/*` and strips the `/h5p` prefix before proxying.
 *     Therefore, all routes below are implemented *without* the `/h5p` prefix.
 *   - `GET /healthz` returns a readiness probe (no auth).
 *   - `GET /auth/me` mirrors `GET <GUSTAV_WEB_INTERNAL_BASE>/api/me` (cookie forwarded).
 *   - `POST /contents/import` (teacher/admin only) imports a `.h5p` package and returns `content_id`.
 *   - `GET /contents/:contentId/export` (teacher/admin only) exports a `.h5p` package.
 *   - `GET /libraries` (teacher/admin only) lists installed content-type libraries.
 *   - `POST /libraries/import` (teacher/admin only) installs a content-type library package.
 *   - `GET /player?content_id=...` (admin only) is a standalone debug page for the player.
 *   - `GET /player/model?content_id=...` (student/teacher/admin) returns the JSON model for `<h5p-player>`.
 *   - `GET /editor` (admin only) is a standalone debug page for the editor.
 *   - `GET /editor/model` (teacher/admin) returns the JSON model for `<h5p-editor>`.
 *
 * Security notes:
 *   - "Fail closed": if auth cannot be proven, respond 401/403.
 *   - CSP is strict by default (no `*`, no `unsafe-eval`). Standalone debug HTML
 *     pages override CSP to allow the inline scripts they currently contain.
 *   - Trusted-content model: H5P packages are treated as executable code.
 *     Only role `teacher` (and `admin`) may import/export packages.
 *   - Write routes require strict same-origin checks via Origin/Referer.
 */

import path from "node:path";
import { createHmac, timingSafeEqual } from "node:crypto";
import { access, mkdir, readdir, unlink, writeFile } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import express from "express";
import multer from "multer";
import { normalizeH5PAjaxBody } from "./lib/ajax_body.mjs";
import { buildSessionCookieHeader } from "./lib/cookies.mjs";
import { debugPagesEnabled, isProdLikeEnv } from "./lib/env.mjs";
import { fetchWithTimeout } from "./lib/fetch_timeout.mjs";
import { createFinishedForwardingMetrics, forwardLearningSubmission } from "./lib/finished_forwarding.mjs";
import {
  buildFinishedSubmissionIdempotencyKey,
  parseOriginForForwarding,
} from "./lib/finished_submission_context.mjs";
import {
  authenticateInternalTeacher,
  isInternalAuth,
  rolesAllowAdmin,
  rolesAllowStudentOrTeacher,
  rolesAllowTeacher,
} from "./lib/internal_auth.mjs";

const port = Number.parseInt(process.env.PORT || "3000", 10);
const gustavWebInternalBase = process.env.GUSTAV_WEB_INTERNAL_BASE || "http://web:8000";
const gustavFrontendInternalBase = process.env.GUSTAV_FRONTEND_INTERNAL_BASE || "http://gustav-frontend:3000";
const sessionCookieName = process.env.SESSION_COOKIE_NAME || "gustav_session";
const frontendSessionCookieName = process.env.FRONTEND_SESSION_COOKIE_NAME || "gustav_bff_session";
const authCacheTtlSeconds = Number.parseInt(process.env.AUTH_CACHE_TTL_SECONDS || "30", 10);
const AUTH_CACHE_MAX_ENTRIES = parseMaxEntries(process.env.AUTH_CACHE_MAX_ENTRIES, 1000);
const H5P_AUTH_CACHE_MAX_ENTRIES = parseMaxEntries(process.env.H5P_AUTH_CACHE_MAX_ENTRIES, 5000);
const storageRoot = process.env.H5P_STORAGE_ROOT || "/data/h5p";
const uploadMaxBytes = Number.parseInt(
  process.env.H5P_MAX_UPLOAD_BYTES || String(100 * 1024 * 1024),
  10,
);
const themeStylesheetPath = "/h5p/theme/h5p-gustav.css";
const reviewTokenSecret = String(process.env.H5P_REVIEW_TOKEN_SECRET || "").trim();
const h5pInternalSharedSecret = String(process.env.H5P_INTERNAL_SHARED_SECRET || "").trim();
const gustavEnv = String(process.env.GUSTAV_ENV || "dev").trim().toLowerCase();
const isProdLike = isProdLikeEnv(gustavEnv);
const upstreamFetchTimeoutMsRaw = Number.parseInt(process.env.H5P_UPSTREAM_FETCH_TIMEOUT_MS || "5000", 10);
const upstreamFetchTimeoutMs =
  Number.isFinite(upstreamFetchTimeoutMsRaw) && upstreamFetchTimeoutMsRaw > 0 ? upstreamFetchTimeoutMsRaw : 5000;
const debugHtmlEnabled = debugPagesEnabled({
  gustavEnv,
  enableFlag: process.env.H5P_ENABLE_DEBUG_PAGES,
});
if (isProdLike && (!reviewTokenSecret || reviewTokenSecret.toUpperCase().startsWith("CHANGE_ME"))) {
  // eslint-disable-next-line no-console
  console.error(
    "Refusing to start: H5P_REVIEW_TOKEN_SECRET is unset or a placeholder in production/staging.",
  );
  process.exit(1);
}
if (isProdLike && (!h5pInternalSharedSecret || h5pInternalSharedSecret.toUpperCase().startsWith("CHANGE_ME"))) {
  // eslint-disable-next-line no-console
  console.error(
    "Refusing to start: H5P_INTERNAL_SHARED_SECRET is unset or a placeholder in production/staging.",
  );
  process.exit(1);
}

const storageDirs = {
  root: storageRoot,
  libraries: path.join(storageRoot, "libraries"),
  content: path.join(storageRoot, "content"),
  tmp: path.join(storageRoot, "tmp"),
  userdata: path.join(storageRoot, "userdata"),
  uploads: path.join(storageRoot, "uploads"),
};

/**
 * Cache auth lookups for short bursts (editor/player loads many assets quickly).
 * Key: session id. Value: { expiresAtMs, payload }
 */
const authCache = new Map();

/**
 * Cache H5P content authorization checks (student scope).
 * Key: `${session_id}|${course_id}|${content_id}`. Value: { expiresAtMs, allowed: boolean }
 */
const h5pContentAccessCache = new Map();

/**
 * Best-effort forwarding telemetry for:
 *   H5P `POST /finishedData` → Learning `POST /api/learning/.../submissions`.
 *
 * Why:
 *   Forwarding failures must be observable without logging PII or response bodies.
 */
const finishedForwardingMetrics = createFinishedForwardingMetrics();

// Default CSP for all `/h5p/*` responses (strict, no wildcards, no unsafe-eval).
//
// Note:
//   In the primary GUSTAV flow, the H5P editor/player runs embedded inside
//   regular GUSTAV pages (Lumi webcomponents). In that embedded mode, the
//   browser enforces the *app* CSP for script execution.
//
//   This CSP is still valuable as defense-in-depth for standalone HTML pages
//   served by the H5P service (especially the admin-only debug pages).
const CSP_DEFAULT = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  "script-src 'self'",
  // H5P uses inline styles and style attributes widely. We keep this
  // permission scoped to the H5P service (not the whole app).
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' data: blob:",
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
].join("; ");

// Scoped CSP exception for standalone debug HTML pages only.
// Those pages currently contain inline <script> and an inline import map.
const CSP_DEBUG_HTML = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' data: blob:",
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
].join("; ");

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  // Align with the main app: keep a useful Referer for same-origin requests,
  // and only send the *origin* on cross-origin requests (no path leaks).
  //
  // Why:
  //   Some H5P embed modes may end up with `Origin: null` (sandboxed iframes).
  //   In those cases we still want a same-origin indicator for CSRF checks.
  "Referrer-Policy": "strict-origin-when-cross-origin",
  // Default CSP is strict. The standalone debug pages override it with CSP_DEBUG_HTML.
  "Content-Security-Policy": CSP_DEFAULT,
};

function ensureThemeStylesLast(styles) {
  const arr = Array.isArray(styles) ? styles.filter((s) => s !== themeStylesheetPath) : [];
  arr.push(themeStylesheetPath);
  return arr;
}

function ensureDivEmbedTypes(embedTypes) {
  // Lumi's `<h5p-player>` prefers DIV when possible (less iframes, better theming).
  // In practice many H5P packages advertise `embedTypes=["iframe"]` only, which
  // forces an internal iframe and makes a native GUSTAV theme almost impossible
  // (tokens do not automatically exist inside the iframe).
  //
  // We therefore advertise `div` as supported for the embedded player UI.
  const raw = Array.isArray(embedTypes) ? embedTypes : [];
  const out = ["div"];
  for (const t of raw) {
    if (!t) continue;
    if (t === "div") continue;
    if (out.includes(t)) continue;
    out.push(t);
  }
  return out;
}

function sendJson(res, statusCode, body, headers = {}) {
  res.status(statusCode);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
  res.setHeader("Cache-Control", "private, no-store");
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  res.json(body);
}

function sendHtml(res, statusCode, html, headers = {}) {
  res.status(statusCode);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
  res.setHeader("Cache-Control", "private, no-store");
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  res.type("html").send(html);
}

function requireDebugHtmlEnabled(_req, res, next) {
  if (debugHtmlEnabled) return next();
  sendHtml(res, 404, "");
}

function asyncHandler(fn) {
  // Express 4 does not automatically handle rejected promises from async
  // handlers. Wrap them so errors propagate to the error middleware.
  return function wrapped(req, res, next) {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(";")) {
    const [rawKey, ...rawRest] = part.trim().split("=");
    if (!rawKey) continue;
    const rawValue = rawRest.join("=");
    // decodeURIComponent can throw on malformed percent encodings; treat such
    // values as opaque and keep the raw string to avoid a 500.
    let decoded = rawValue;
    try {
      decoded = decodeURIComponent(rawValue);
    } catch {
      decoded = rawValue;
    }
    out[rawKey] = decoded;
  }
  return out;
}

function parseMaxEntries(raw, defaultValue) {
  const n = Number.parseInt(String(raw || "").trim(), 10);
  if (!Number.isFinite(n) || n < 0) return defaultValue;
  return n;
}

function pruneCacheToMaxEntries(cache, nowMs, maxEntries) {
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

function sanitizeHeaderFilename(value) {
  // Content-Disposition is a response header and must never contain control
  // characters (CR/LF). Node would reject invalid header chars, causing 500s.
  // We keep this KISS: map to a conservative ASCII token.
  const raw = String(value || "").trim();
  const safe = raw.replace(/[^a-zA-Z0-9._-]/g, "_").replace(/_+/g, "_").slice(0, 80);
  return safe || "download";
}

function parseReviewToken(token) {
  if (!reviewTokenSecret) return null;
  if (typeof token !== "string" || !token) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [payloadB64, sigB64] = parts;
  let payloadBytes;
  let sigBytes;
  try {
    payloadBytes = Buffer.from(payloadB64, "base64url");
    sigBytes = Buffer.from(sigB64, "base64url");
  } catch {
    return null;
  }

  try {
    const expected = createHmac("sha256", reviewTokenSecret).update(payloadBytes).digest();
    if (sigBytes.length !== expected.length) return null;
    if (!timingSafeEqual(sigBytes, expected)) return null;
  } catch {
    return null;
  }

  let obj;
  try {
    obj = JSON.parse(payloadBytes.toString("utf-8"));
  } catch {
    return null;
  }
  if (!obj || typeof obj !== "object") return null;

  const teacherSub = obj.teacher_sub;
  const studentSub = obj.student_sub;
  const courseId = obj.course_id;
  const taskId = obj.task_id;
  const contentId = obj.content_id;
  const exp = obj.exp;

  if (typeof teacherSub !== "string" || !teacherSub) return null;
  if (typeof studentSub !== "string" || !studentSub) return null;
  if (typeof courseId !== "string" || !courseId) return null;
  if (typeof taskId !== "string" || !taskId) return null;
  if (typeof contentId !== "string" || !contentId) return null;
  if (typeof exp !== "number" || !Number.isFinite(exp)) return null;
  const now = Math.floor(Date.now() / 1000);
  if (exp <= now) return null;

  return { teacherSub, studentSub, courseId, taskId, contentId, exp };
}

function getPublicOrigin(req) {
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

function requireSameOrigin(req, res, next) {
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

  const originIsNull = origin.trim().toLowerCase() === "null";
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
  if (origin && !originIsNull) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  // Fallback: accept same-origin Referer (important when Origin is `null`).
  if (!refererMatches) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  next();
}

async function probeStorage() {
  try {
    await mkdir(storageDirs.libraries, { recursive: true });
    await mkdir(storageDirs.content, { recursive: true });
    await mkdir(storageDirs.tmp, { recursive: true });
    await mkdir(storageDirs.userdata, { recursive: true });
    await mkdir(storageDirs.uploads, { recursive: true });
    await access(storageDirs.tmp, fsConstants.W_OK);
    return { ok: true, root: storageDirs.root };
  } catch (err) {
    return { ok: false, root: storageDirs.root, error: String(err) };
  }
}

async function fetchGustavMe(cookieHeader) {
  const backendUrl = `${gustavWebInternalBase.replace(/\/+$/, "")}/api/me`;
  const frontendUrl = `${gustavFrontendInternalBase.replace(/\/+$/, "")}/internal/h5p/me`;
  const sessionCookieHeader = buildSessionCookieHeader(cookieHeader, sessionCookieName);
  const frontendCookieHeader = buildSessionCookieHeader(cookieHeader, frontendSessionCookieName);

  const backendHeaders = {
    "cache-control": "no-store",
  };
  if (sessionCookieHeader) backendHeaders.cookie = sessionCookieHeader;

  if (sessionCookieHeader) {
    const r = await fetchWithTimeout(backendUrl, { method: "GET", headers: backendHeaders }, { timeoutMs: upstreamFetchTimeoutMs });
    if (r.status === 200) {
      const payload = await r.json();
      return { ok: true, payload };
    }
    if (!frontendCookieHeader || r.status !== 401) {
      return { ok: false, status: r.status };
    }
  }

  if (!frontendCookieHeader) {
    return { ok: false, status: 401 };
  }

  const frontendHeaders = {
    "cache-control": "no-store",
    cookie: frontendCookieHeader,
  };
  const r = await fetchWithTimeout(frontendUrl, { method: "GET", headers: frontendHeaders }, { timeoutMs: upstreamFetchTimeoutMs });
  if (r.status !== 200) {
    return { ok: false, status: r.status };
  }
  const payload = await r.json();
  return { ok: true, payload };
}

async function checkLearningH5PContentAccess(courseId, contentId, cookieHeader) {
  const backendBase = gustavWebInternalBase.replace(/\/+$/, "");
  const frontendBase = gustavFrontendInternalBase.replace(/\/+$/, "");
  const url = `${backendBase}/api/learning/courses/${encodeURIComponent(courseId)}/h5p/contents/${encodeURIComponent(contentId)}/access`;
  const frontendUrl =
    `${frontendBase}/internal/h5p/access?course_id=${encodeURIComponent(courseId)}&content_id=${encodeURIComponent(contentId)}`;
  const sessionCookieHeader = buildSessionCookieHeader(cookieHeader, sessionCookieName);
  const frontendCookieHeader = buildSessionCookieHeader(cookieHeader, frontendSessionCookieName);
  const headers = {
    "cache-control": "no-store",
  };
  if (sessionCookieHeader) headers.cookie = sessionCookieHeader;
  try {
    if (sessionCookieHeader) {
      const r = await fetchWithTimeout(url, { method: "GET", headers }, { timeoutMs: upstreamFetchTimeoutMs });
      if (r.status === 204) {
        return { ok: true, status: 204 };
      }
      if (!frontendCookieHeader || r.status !== 401) {
        return { ok: false, status: r.status };
      }
    }

    if (!frontendCookieHeader) {
      return { ok: false, status: 401 };
    }

    const frontendHeaders = {
      "cache-control": "no-store",
      cookie: frontendCookieHeader,
    };
    const r = await fetchWithTimeout(
      frontendUrl,
      { method: "GET", headers: frontendHeaders },
      { timeoutMs: upstreamFetchTimeoutMs },
    );
    if (r.status === 204) {
      return { ok: true, status: 204 };
    }
    return { ok: false, status: r.status };
  } catch {
    // Upstream network errors: fail-closed in the caller (student context).
    return { ok: false, status: 503 };
  }
}

async function requireAuth(req, res, next) {
  if (authenticateInternalTeacher(req, h5pInternalSharedSecret)) {
    next();
    return;
  }

  const cookieHeader = req.get("cookie") || "";
  const cookies = parseCookies(cookieHeader);
  const legacySessionId = cookies[sessionCookieName];
  const frontendSessionId = cookies[frontendSessionCookieName];
  const authCacheKey = legacySessionId || (frontendSessionId ? `bff:${frontendSessionId}` : "");
  if (!authCacheKey) {
    sendJson(res, 401, { error: "unauthenticated" });
    return;
  }

  const now = Date.now();
  const cached = authCache.get(authCacheKey);
  if (cached && cached.expiresAtMs > now) {
    // LRU touch: move to end so pruning removes older entries first.
    authCache.delete(authCacheKey);
    authCache.set(authCacheKey, cached);

    req.gustavMe = cached.payload;
    req.user = {
      id: cached.payload.sub,
      name: cached.payload.name || cached.payload.sub,
      email: `${cached.payload.sub}@local.invalid`,
      type: "local",
    };
    req.language = "en";
    next();
    return;
  }
  if (cached) authCache.delete(authCacheKey);

  try {
    const me = await fetchGustavMe(cookieHeader);
    if (!me.ok) {
      if (me.status === 401) {
        sendJson(res, 401, { error: "unauthenticated" });
        return;
      }
      sendJson(res, 502, { error: "upstream_unavailable" });
      return;
    }
    authCache.delete(authCacheKey);
    authCache.set(authCacheKey, { expiresAtMs: now + authCacheTtlSeconds * 1000, payload: me.payload });
    pruneCacheToMaxEntries(authCache, now, AUTH_CACHE_MAX_ENTRIES);
    req.gustavMe = me.payload;
    req.user = {
      id: me.payload.sub,
      name: me.payload.name || me.payload.sub,
      email: `${me.payload.sub}@local.invalid`,
      type: "local",
    };
    req.language = "en";
    next();
    return;
  } catch {
    sendJson(res, 502, { error: "upstream_unavailable" });
    return;
  }
}

function requireStudentOrTeacher(req, res, next) {
  if (!rolesAllowStudentOrTeacher(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}

function requireTeacher(req, res, next) {
  if (!rolesAllowTeacher(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}

function requireAdmin(req, res, next) {
  if (!rolesAllowAdmin(req.gustavMe?.roles)) {
    sendJson(res, 403, { error: "forbidden" });
    return;
  }
  next();
}

function getMainLibraryUbername(metadata) {
  const machineName = metadata?.mainLibrary;
  const deps = metadata?.preloadedDependencies || [];
  const found = deps.find((d) => d.machineName === machineName);
  if (!machineName || !found) return null;
  return `${machineName} ${found.majorVersion}.${found.minorVersion}`;
}

async function listInstalledLibraries() {
  try {
    const entries = await readdir(storageDirs.libraries, { withFileTypes: true });
    const libs = [];
    for (const ent of entries) {
      if (!ent.isDirectory()) continue;
      const m = /^(.+)-(\d+)\.(\d+)$/.exec(ent.name);
      if (!m) continue;
      libs.push({
        ubername: ent.name,
        machine_name: m[1],
        major_version: Number.parseInt(m[2], 10),
        minor_version: Number.parseInt(m[3], 10),
      });
    }
    libs.sort((a, b) => a.ubername.localeCompare(b.ubername));
    return libs;
  } catch {
    return [];
  }
}

const uploadImport = multer({
  storage: multer.diskStorage({
    destination: storageDirs.uploads,
    filename: (_req, file, cb) => {
      const safeBase = String(file.originalname || "upload.h5p")
        .replace(/[^a-zA-Z0-9._-]/g, "_")
        .slice(0, 80);
      cb(null, `${Date.now()}-${Math.random().toString(16).slice(2)}-${safeBase}`);
    },
  }),
  limits: { fileSize: uploadMaxBytes },
});

const uploadAjax = multer({
  storage: multer.diskStorage({
    destination: storageDirs.uploads,
    filename: (_req, file, cb) => {
      const safeBase = String(file.originalname || "upload.bin")
        .replace(/[^a-zA-Z0-9._-]/g, "_")
        .slice(0, 80);
      cb(null, `${Date.now()}-${Math.random().toString(16).slice(2)}-${safeBase}`);
    },
  }),
  limits: { fileSize: uploadMaxBytes },
}).fields([
  { name: "file", maxCount: 1 },
  { name: "h5p", maxCount: 1 },
]);

function maybeParseAjaxFiles(req, res, next) {
  if (req.is("multipart/form-data")) {
    uploadAjax(req, res, next);
    return;
  }
  next();
}

async function main() {
  const H5P = (await import("@lumieducation/h5p-server")).default;
  const H5PExpress = (await import("@lumieducation/h5p-express")).default;
  const { H5PConfig, H5PEditor, H5PPlayer, H5PAjaxEndpoint, fsImplementations } = H5P;
  const { h5pAjaxExpressRouter } = H5PExpress;

  const storage = await probeStorage();
  if (!storage.ok) {
    // eslint-disable-next-line no-console
    console.error(`H5P storage not ready: ${storage.error}`);
    process.exit(1);
  }

  const configPath = path.join(storageRoot, "h5p-config.json");
  try {
    await access(configPath, fsConstants.R_OK);
  } catch {
    await writeFile(configPath, "{}", "utf-8");
  }
  const configStorage = await fsImplementations.JsonStorage.create(configPath);
  const h5pConfig = new H5PConfig(configStorage, {
    baseUrl: "/h5p",
    // Avoid conflicting with the human-facing editor page at GET /editor.
    // The H5P editor core files are served under this URL instead.
    editorLibraryUrl: "/editor-assets",
    // Avoid embedding external hub URLs into HTML/JSON responses (offline-first).
    // Hub fetching remains disabled in Phase 1.
    contentHubContentEndpoint: "/h5p/hub-api",
    // Hard-disable all automatic hub fetching in Phase 1 (offline-first).
    fetchingDisabled: 1,
    // Allow large packages if storage permits (still bounded by service limits).
    maxFileSize: uploadMaxBytes,
    maxTotalSize: uploadMaxBytes,
  });
  await h5pConfig.load();

  const cache = new fsImplementations.InMemoryStorage();
  const libraryStorage = new fsImplementations.FileLibraryStorage(storageDirs.libraries);
  const contentStorage = new fsImplementations.FileContentStorage(storageDirs.content, {
    maxPathLength: h5pConfig.exportMaxContentPathLength,
  });
  const tmpStorage = new fsImplementations.DirectoryTemporaryFileStorage(storageDirs.tmp);
  const userDataStorage = new fsImplementations.FileContentUserDataStorage(storageDirs.userdata);

  const h5pEditor = new H5PEditor(
    cache,
    h5pConfig,
    libraryStorage,
    contentStorage,
    tmpStorage,
    undefined,
    undefined,
    undefined,
    userDataStorage,
  );
  const h5pPlayer = new H5PPlayer(
    libraryStorage,
    contentStorage,
    h5pConfig,
    undefined,
    undefined,
    undefined,
    undefined,
    userDataStorage,
  );
  const h5pAjax = new H5PAjaxEndpoint(h5pEditor);

  // We don't use the built-in SSR renderer. Instead, we expose editor/player pages
  // that use Lumi's web components and a small JSON "editor model" endpoint.
  h5pEditor.setRenderer((model) => ({
    integration: model.integration,
    scripts: model.scripts,
    styles: model.styles,
  }));
  h5pPlayer.setRenderer((model) => ({
    contentId: String(model.contentId),
    embedTypes: model.embedTypes,
    integration: model.integration,
    scripts: model.scripts,
    styles: model.styles,
    translations: model.translations,
    user: model.user,
  }));

  const app = express();
  app.disable("x-powered-by");
  const trustProxyEnabled = String(process.env.H5P_TRUST_PROXY || "")
    .trim()
    .toLowerCase() === "true";
  if (trustProxyEnabled) {
    // We only expect a single reverse-proxy hop (Caddy). Do not trust arbitrary clients.
    app.set("trust proxy", 1);
  }

  // Security headers for all responses (Cache-Control is set route-specific).
  app.use((req, res, next) => {
    for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
    next();
  });

  // Body parsing for H5P Ajax endpoints (user state / finished data).
  app.use(express.json({ limit: "2mb" }));
  app.use(express.urlencoded({ extended: false, limit: "2mb" }));

  // Public readiness probe (used by E2E and docker-compose health checks).
  app.get("/healthz", asyncHandler(async (_req, res) => {
    const storage = await probeStorage();
    sendJson(res, storage.ok ? 200 : 503, {
      status: storage.ok ? "healthy" : "unhealthy",
      service: "gustav-h5p",
      time: new Date().toISOString(),
      // Keep the public payload minimal (no filesystem paths, no raw errors).
      storage: { ok: storage.ok },
    });
  }));

  // Public browser runtime assets.
  //
  // These files must stay reachable without a session cookie because the
  // browser needs them before the authenticated H5P model endpoints can render
  // any visible editor/player UI.
  // Overrides for Lumi webcomponents to keep browser ESM compatible without a bundler.
  // These files remove bare imports like `deepmerge` and `await-lock`.
  app.use(
    "/webcomponents",
    express.static(path.join("/app", "vendor", "webcomponents", "overrides"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned → always revalidate (prevents stale JS after redeploys).
      maxAge: 0,
      extensions: ["js"],
    }),
  );

  // Serve Lumi web components (ES modules).
  app.use(
    "/webcomponents",
    express.static(
      path.join("/app", "node_modules", "@lumieducation", "h5p-webcomponents", "build", "es2015"),
      // Note: Lumi's ES2015 build uses extensionless relative imports like
      // `import ... from './h5p-editor'`. Browsers do not auto-append `.js`,
      // so we enable a `.js` fallback to make those imports resolve.
      // Not versioned → always revalidate (prevents stale JS after redeploys).
      { cacheControl: true, etag: true, lastModified: true, maxAge: 0, extensions: ["js"] },
    ),
  );

  // Global H5P theme overrides (Option B).
  app.use(
    "/theme",
    express.static(path.join("/app", "vendor", "theme"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned → always revalidate (prevents stale CSS after redeploys).
      maxAge: 0,
      extensions: ["css"],
    }),
  );

  // Vendor shims required by the webcomponents when used directly in a browser
  // (without a bundler). The upstream build has bare imports like `deepmerge`
  // and `await-lock`, which must be resolved via an import map.
  app.use(
    "/webcomponents/vendor",
    express.static(path.join("/app", "vendor", "webcomponents"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned → always revalidate (prevents stale JS after redeploys).
      maxAge: 0,
    }),
  );

  // Everything else is authenticated.
  app.use(requireAuth);
  app.use(requireStudentOrTeacher);

  // Teacher review "view as student" (read-only) for H5P user state.
  //
  // The embedded review player rewrites the `contentUserData` URL to include
  // a short-lived `review_token`. For those requests we:
  // - validate the token (fail-closed),
  // - bind it to the authenticated teacher, and
  // - impersonate the student for GET-only reads.
  app.use((req, res, next) => {
    const reviewToken = typeof req.query.review_token === "string" ? req.query.review_token : undefined;
    if (!reviewToken) {
      next();
      return;
    }
    // The model endpoint validates the token separately and must see the real teacher user.
    if (req.path === "/player/review") {
      next();
      return;
    }

    // Defense-in-depth: review is teacher-only.
    if (!rolesAllowTeacher(req.gustavMe?.roles)) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    // Review token must be valid and match the authenticated teacher.
    const payload = parseReviewToken(reviewToken);
    if (!payload) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    if (payload.teacherSub !== req.user?.id) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    // Strict read-only: block all non-GET requests when a review token is present.
    if (req.method !== "GET") {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    // Fail-closed: only allow the token to be used for content user data reads.
    const m = req.path.match(/\/contentUserData\/([^/]+)/);
    const contentIdFromPath = m?.[1] ? String(m[1]) : "";
    if (!contentIdFromPath) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    if (contentIdFromPath !== payload.contentId) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    // Optional context binding: enforce when the runtime forwards it.
    const contextId =
      typeof req.query.contextId === "string"
        ? req.query.contextId
        : typeof req.query.context_id === "string"
          ? req.query.context_id
          : "";
    if (contextId && contextId !== payload.taskId) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    // Impersonate the student for GET reads so the runtime loads the student's state.
    req.user = {
      id: payload.studentSub,
      name: payload.studentSub,
      email: `${payload.studentSub}@local.invalid`,
      type: "local",
    };

    next();
  });

  app.get("/auth/me", (req, res) => {
    sendJson(res, 200, req.gustavMe);
  });

  app.get("/editor", requireDebugHtmlEnabled, requireAdmin, (_req, res) => {
    sendHtml(
      res,
      200,
      [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\" />",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        "<title>H5P Editor (Phase 1)</title>",
        "<style>",
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;line-height:1.35;padding:16px;max-width:980px;margin:0 auto}",
        "code{background:#f5f5f5;padding:0 4px;border-radius:4px}",
        "input,button{font:inherit}",
        ".row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}",
        ".box{border:1px solid #ddd;border-radius:8px;padding:12px;margin:12px 0}",
        ".muted{color:#666}",
        "</style>",
        "</head><body>",
        "<h1>H5P Editor (Phase 1)</h1>",
        "<p class=\"muted\">Admin-only debug UI. Trusted-content model: only <code>teacher</code>/<code>admin</code> may install libraries and create/update content.</p>",
        "<div class=\"box\">",
        "<h2>1) Install content-type libraries (admin-managed)</h2>",
        "<p>If you see <code>missing_libraries</code> on import, install the missing libraries first.</p>",
        "<form method=\"post\" enctype=\"multipart/form-data\" action=\"/h5p/libraries/import\">",
        "<input type=\"file\" name=\"file\" accept=\".h5p,application/zip\" required />",
        "<button type=\"submit\">Install library package (.h5p)</button>",
        "</form>",
        "<p><a href=\"/h5p/libraries\">List installed libraries</a></p>",
        "</div>",
        "<div class=\"box\">",
        "<h2>2) Import content package (.h5p)</h2>",
        "<form method=\"post\" enctype=\"multipart/form-data\" action=\"/h5p/contents/import\">",
        "<input type=\"file\" name=\"file\" accept=\".h5p,application/zip\" required />",
        "<button type=\"submit\">Import .h5p</button>",
        "</form>",
        "</div>",
        "<div class=\"box\">",
        "<h2>3) Create / edit content (web editor)</h2>",
        "<div class=\"row\">",
        "<label>Content ID <input id=\"contentId\" placeholder=\"(empty = new)\" size=\"22\" /></label>",
        "<button id=\"loadNew\" type=\"button\">New</button>",
        "<button id=\"loadExisting\" type=\"button\">Load</button>",
        "<button id=\"save\" type=\"button\">Save</button>",
        "</div>",
        "<p id=\"status\" class=\"muted\">Waiting for editor JS…</p>",
        "<h5p-editor id=\"h5pEditor\" content-id=\"new\"></h5p-editor>",
        "<script>",
        "(() => {",
        "  const el = document.getElementById('status');",
        "  const set = (msg) => { if (el) el.textContent = msg || ''; };",
        "  set('Loading editor UI…');",
        "  window.addEventListener('error', (ev) => {",
        "    const msg = ev?.message || ev?.type || 'unknown error';",
        "    set('JS error: ' + msg);",
        "  });",
        "  window.addEventListener('unhandledrejection', (ev) => {",
        "    const reason = ev?.reason?.message || String(ev?.reason || 'unknown rejection');",
        "    set('JS rejection: ' + reason);",
        "  });",
        "  setTimeout(() => {",
        "    if (!window.customElements?.get('h5p-editor')) {",
        "      set('Editor JS did not initialize (module load failed). Open DevTools Console.');",
        "      return;",
        "    }",
        "    if (!window.__gustav_h5p_editor_init_ok) {",
        "      set('Editor JS loaded, but initialization did not complete. Open DevTools Console.');",
        "    }",
        "  }, 1500);",
        "})();",
        "</script>",
        "<script type=\"importmap\">",
        JSON.stringify({
          imports: {
            deepmerge: "/h5p/webcomponents/vendor/deepmerge.js",
            "await-lock": "/h5p/webcomponents/vendor/await-lock.js",
          },
        }),
        "</script>",
        "<script type=\"module\">",
        "(async () => {",
        "  const status = document.getElementById('status');",
        "  const setStatus = (msg) => { if (status) status.textContent = msg || ''; };",
        "  try {",
        "    setStatus('Initializing editor…');",
        "    const { defineElements } = await import('/h5p/webcomponents/index.js');",
        "    defineElements(['h5p-editor']);",
        "",
        "    const editor = document.getElementById('h5pEditor');",
        "    const contentIdInput = document.getElementById('contentId');",
        "    const btnNew = document.getElementById('loadNew');",
        "    const btnLoad = document.getElementById('loadExisting');",
        "    const btnSave = document.getElementById('save');",
        "    if (!editor) throw new Error('missing element #h5pEditor');",
        "    if (!contentIdInput) throw new Error('missing element #contentId');",
        "    if (!btnNew || !btnLoad || !btnSave) throw new Error('missing one or more buttons');",
        "",
        "    // Workaround: the Lumi webcomponent deliberately does NOT re-render when switching",
        "    // from content-id='new' to an existing id (to avoid flicker when saving new content).",
        "    // For our Phase-1 page we *do* want this switch to load existing content, so we force",
        "    // an attribute transition via `undefined` first.",
        "    const setEditorContentId = (cid) => {",
        "      editor.contentId = undefined;",
        "      editor.contentId = cid;",
        "    };",
        "",
        "    editor.loadContentCallback = async (contentId) => {",
        "      const url = new URL('/h5p/editor/model', window.location.origin);",
        "      if (contentId) url.searchParams.set('content_id', contentId);",
        "      const r = await fetch(url.toString(), { credentials: 'include' });",
        "      if (!r.ok) {",
        "        let msg = `HTTP ${r.status}`;",
        "        try { const j = await r.json(); msg = j?.error || msg; } catch {}",
        "        throw new Error(msg);",
        "      }",
        "      return await r.json();",
        "    };",
        "",
        "    editor.saveContentCallback = async (contentId, requestBody) => {",
        "      const isUpdate = Boolean(contentId);",
        "      const url = isUpdate ? `/h5p/contents/${encodeURIComponent(contentId)}` : '/h5p/contents';",
        "      const method = isUpdate ? 'PATCH' : 'POST';",
        "      const r = await fetch(url, {",
        "        method,",
        "        credentials: 'include',",
        "        headers: { 'Content-Type': 'application/json' },",
        "        body: JSON.stringify(requestBody),",
        "      });",
        "      const data = await r.json().catch(() => ({}));",
        "      if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);",
        "      return { contentId: data.content_id, metadata: data.metadata };",
        "    };",
        "",
        "    btnNew.addEventListener('click', () => {",
        "      contentIdInput.value = '';",
        "      setEditorContentId('new');",
        "      setStatus('Creating new content…');",
        "    });",
        "    btnLoad.addEventListener('click', () => {",
        "      const cid = (contentIdInput.value || '').trim();",
        "      if (!cid) { setStatus('Enter a content id first.'); return; }",
        "      setEditorContentId(cid);",
        "      setStatus(`Loading content ${cid}…`);",
        "    });",
        "    btnSave.addEventListener('click', async () => {",
        "      try {",
        "        setStatus('Saving…');",
        "        const saved = await editor.save();",
        "        if (saved?.contentId) contentIdInput.value = saved.contentId;",
        "      } catch (e) {",
        "        setStatus(String(e?.message || e));",
        "      }",
        "    });",
        "",
        "    editor.addEventListener('editorloaded', (ev) => {",
        "      setStatus(`Editor loaded (${ev?.detail?.ubername || 'unknown library'}).`);",
        "    });",
        "    editor.addEventListener('saved', (ev) => {",
        "      const cid = ev?.detail?.contentId;",
        "      contentIdInput.value = cid || '';",
        "      if (!status) return;",
        "      status.textContent = '';",
        "      if (!cid) { status.textContent = 'Saved.'; return; }",
        "      const code = document.createElement('code');",
        "      code.textContent = cid;",
        "      status.append('Saved content ', code, '. ');",
        "      const a = document.createElement('a');",
        "      a.href = '/h5p/player?content_id=' + encodeURIComponent(cid);",
        "      a.textContent = 'Open player';",
        "      status.append(a);",
        "    });",
        "    editor.addEventListener('save-error', (ev) => {",
        "      setStatus(`Save error: ${ev?.detail?.message || 'unknown'}`);",
        "    });",
        "    editor.addEventListener('validation-error', (ev) => {",
        "      setStatus(`Validation error: ${ev?.detail?.message || 'unknown'}`);",
        "    });",
        "",
        "    window.__gustav_h5p_editor_init_ok = true;",
        "    setStatus('Ready.');",
        "  } catch (e) {",
        "    setStatus('Init failed: ' + String(e?.message || e));",
        "  }",
        "})();",
        "</script>",
        "</div>",
        "</body></html>",
      // IMPORTANT: keep line breaks in the HTML so `//` comments inside the
      // inline `<script type="module">` do not swallow the remainder of the
      // module (the browser treats the whole script as a single line otherwise).
      ].join("\n"),
      { "Content-Security-Policy": CSP_DEBUG_HTML },
    );
  });

  app.get("/editor/model", requireTeacher, asyncHandler(async (req, res) => {
    const contentId =
      typeof req.query.content_id === "string" ? req.query.content_id : undefined;
    if (req.query.content_id !== undefined && !contentId) {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    try {
      const language = typeof req.query.language === "string" ? req.query.language : req.language;
      const model = await h5pEditor.render(contentId, language, req.user);
      const out = { ...model, styles: ensureThemeStylesLast(model?.styles) };
      if (contentId) {
        const content = await h5pEditor.getContent(contentId, req.user);
        out.library = content.library;
        out.metadata = content.h5p;
        out.params = content.params.params;
      }
      sendJson(res, 200, out);
    } catch (err) {
      if (err?.httpStatusCode === 404) {
        sendJson(res, 404, { error: "not_found" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    }
  }));

  app.get("/player/model", asyncHandler(async (req, res) => {
    const contentId =
      typeof req.query.content_id === "string" ? req.query.content_id : undefined;
    if (!contentId) {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    const courseId =
      typeof req.query.course_id === "string" ? req.query.course_id : undefined;
    const contextId =
      typeof req.query.context_id === "string" ? req.query.context_id : undefined;
    const readOnlyStateRaw =
      typeof req.query.read_only_state === "string" ? req.query.read_only_state : undefined;
    const readOnlyState = readOnlyStateRaw === "true";

    // For student requests we require a course scope so we can verify that the
    // content is part of a released H5P task for this course (fail-closed).
    const roles = req.gustavMe?.roles;
    const isTeacher = rolesAllowTeacher(roles);
    const isStudent = Array.isArray(roles) && roles.includes("student") && !isTeacher;
    if (isStudent) {
      if (!courseId) {
        sendJson(res, 403, { error: "forbidden" });
        return;
      }
      const cookieHeader = req.get("cookie") || "";
      const cookies = parseCookies(cookieHeader);
      const authCookie =
        cookies[sessionCookieName] || (cookies[frontendSessionCookieName] ? `bff:${cookies[frontendSessionCookieName]}` : "");
      const cacheKey = `${authCookie}|${courseId}|${contentId}`;
      const now = Date.now();
      let allowed = null;
      const cached = h5pContentAccessCache.get(cacheKey);
      if (cached && cached.expiresAtMs > now) {
        // LRU touch: move to end so pruning removes older entries first.
        h5pContentAccessCache.delete(cacheKey);
        h5pContentAccessCache.set(cacheKey, cached);
        allowed = cached.allowed;
      } else if (cached) {
        h5pContentAccessCache.delete(cacheKey);
      }

      if (allowed === null) {
        const checked = await checkLearningH5PContentAccess(courseId, contentId, cookieHeader);
        if (checked.ok) {
          allowed = true;
          h5pContentAccessCache.delete(cacheKey);
          h5pContentAccessCache.set(cacheKey, { expiresAtMs: now + authCacheTtlSeconds * 1000, allowed: true });
          pruneCacheToMaxEntries(h5pContentAccessCache, now, H5P_AUTH_CACHE_MAX_ENTRIES);
        } else if (checked.status === 404) {
          // Fail-closed: cache negative results briefly to reduce upstream load.
          allowed = false;
          h5pContentAccessCache.delete(cacheKey);
          h5pContentAccessCache.set(cacheKey, { expiresAtMs: now + authCacheTtlSeconds * 1000, allowed: false });
          pruneCacheToMaxEntries(h5pContentAccessCache, now, H5P_AUTH_CACHE_MAX_ENTRIES);
        } else if (checked.status === 401) {
          sendJson(res, 401, { error: "unauthenticated" });
          return;
        } else {
          // Upstream errors: fail-closed and do not reveal whether the content exists.
          sendJson(res, 404, { error: "not_found" });
          return;
        }
      }
      if (!allowed) {
        // Fail-closed: do not reveal whether the content exists in H5P storage.
        sendJson(res, 404, { error: "not_found" });
        return;
      }
    }

    try {
      const language = typeof req.query.language === "string" ? req.query.language : req.language;
      const model = await h5pPlayer.render(contentId, req.user, language, {
        showDownloadButton: false,
        showEmbedButton: false,
        showCopyButton: false,
        showLicenseButton: false,
        contextId,
        readOnlyState,
      });
      const out = {
        ...model,
        embedTypes: ensureDivEmbedTypes(model?.embedTypes),
        styles: ensureThemeStylesLast(model?.styles),
      };
      // Robust progress ingest:
      // Attach course/task context to the `setFinished` endpoint so the H5P
      // service can persist a `learning_submissions(kind='h5p')` row server-side.
      // This avoids relying solely on browser xAPI events (which can be flaky).
      if (courseId && contextId && out?.integration?.ajax?.setFinished) {
        try {
          const base = "http://local.invalid";
          const u = new URL(String(out.integration.ajax.setFinished), base);
          u.searchParams.set("course_id", String(courseId));
          u.searchParams.set("task_id", String(contextId));
          out.integration.ajax.setFinished = `${u.pathname}${u.search || ""}`;
        } catch {
          // Do not fail content loading when URL parsing fails.
        }
      }
      sendJson(res, 200, out);
    } catch (err) {
      if (err?.httpStatusCode === 404) {
        sendJson(res, 404, { error: "not_found" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    }
  }));

  app.get("/player/review", requireTeacher, asyncHandler(async (req, res) => {
    const contentId =
      typeof req.query.content_id === "string" ? req.query.content_id : undefined;
    const contextId =
      typeof req.query.context_id === "string" ? req.query.context_id : undefined;
    const reviewToken =
      typeof req.query.review_token === "string" ? req.query.review_token : undefined;

    if (!contentId || !contextId || !reviewToken) {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    const payload = parseReviewToken(reviewToken);
    if (!payload) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    // Bind token to the authenticated teacher (prevents token re-use by other teachers).
    if (payload.teacherSub !== req.user?.id) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    // Bind content and task context (fail-closed).
    if (payload.contentId !== contentId || payload.taskId !== contextId) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }

    try {
      const language = typeof req.query.language === "string" ? req.query.language : req.language;
      const studentUser = {
        id: payload.studentSub,
        name: payload.studentSub,
        email: `${payload.studentSub}@local.invalid`,
        type: "local",
      };
      const model = await h5pPlayer.render(contentId, studentUser, language, {
        showDownloadButton: false,
        showEmbedButton: false,
        showCopyButton: false,
        showLicenseButton: false,
        contextId,
        // Review mode is always strict read-only.
        readOnlyState: true,
      });
      const out = {
        ...model,
        embedTypes: ensureDivEmbedTypes(model?.embedTypes),
        styles: ensureThemeStylesLast(model?.styles),
      };

      // Do not expose a finished-data endpoint in review mode (strict read-only).
      if (out?.integration?.ajax?.setFinished) {
        try {
          delete out.integration.ajax.setFinished;
        } catch {
          // ignore
        }
      }

      // Ensure subsequent userState reads carry the review token so we can
      // impersonate the student server-side (GET-only).
      if (out?.integration?.ajax?.contentUserData) {
        try {
          const base = "http://local.invalid";
          const u = new URL(String(out.integration.ajax.contentUserData), base);
          u.searchParams.set("review_token", String(reviewToken));
          // Optional: forward the task context for defense-in-depth checks.
          u.searchParams.set("context_id", String(contextId));
          out.integration.ajax.contentUserData = `${u.pathname}${u.search || ""}`;
        } catch {
          // Do not fail model loading when URL parsing fails.
        }
      }

      sendJson(res, 200, out);
    } catch (err) {
      if (err?.httpStatusCode === 404) {
        sendJson(res, 404, { error: "not_found" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    }
  }));

  app.post("/contents", requireTeacher, requireSameOrigin, asyncHandler(async (req, res) => {
    const library = req.body?.library;
    const params = req.body?.params;
    const parameters = params?.params;
    const metadata = params?.metadata;
    if (typeof library !== "string" || !library || typeof parameters !== "object" || !parameters) {
      sendJson(res, 400, { error: "invalid_request" }, { Vary: "Origin" });
      return;
    }
    if (typeof metadata !== "object" || !metadata) {
      sendJson(res, 400, { error: "invalid_request" }, { Vary: "Origin" });
      return;
    }

    try {
      const result = await h5pEditor.saveOrUpdateContentReturnMetaData(
        undefined,
        parameters,
        metadata,
        library,
        req.user,
      );
      sendJson(res, 201, { content_id: String(result.id), metadata: result.metadata }, { Vary: "Origin" });
    } catch (err) {
      if (err?.httpStatusCode) {
        sendJson(res, err.httpStatusCode, { error: err.errorId || "h5p_error" }, { Vary: "Origin" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" }, { Vary: "Origin" });
    }
  }));

  app.patch("/contents/:contentId", requireTeacher, requireSameOrigin, asyncHandler(async (req, res) => {
    const { contentId } = req.params;
    if (!(await contentStorage.contentExists(contentId))) {
      sendJson(res, 404, { error: "not_found" }, { Vary: "Origin" });
      return;
    }

    const library = req.body?.library;
    const params = req.body?.params;
    const parameters = params?.params;
    const metadata = params?.metadata;
    if (typeof library !== "string" || !library || typeof parameters !== "object" || !parameters) {
      sendJson(res, 400, { error: "invalid_request" }, { Vary: "Origin" });
      return;
    }
    if (typeof metadata !== "object" || !metadata) {
      sendJson(res, 400, { error: "invalid_request" }, { Vary: "Origin" });
      return;
    }

    try {
      const result = await h5pEditor.saveOrUpdateContentReturnMetaData(
        contentId,
        parameters,
        metadata,
        library,
        req.user,
      );
      sendJson(res, 200, { content_id: String(result.id), metadata: result.metadata }, { Vary: "Origin" });
    } catch (err) {
      if (err?.httpStatusCode) {
        sendJson(res, err.httpStatusCode, { error: err.errorId || "h5p_error" }, { Vary: "Origin" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" }, { Vary: "Origin" });
    }
  }));

  app.get("/libraries", requireTeacher, asyncHandler(async (_req, res) => {
    const storage = await probeStorage();
    if (!storage.ok) {
      sendJson(res, 503, { error: "storage_unavailable" });
      return;
    }
    const libraries = await listInstalledLibraries();
    sendJson(res, 200, { libraries });
  }));

  app.post(
    "/libraries/import",
    requireTeacher,
    requireSameOrigin,
    uploadImport.single("file"),
    asyncHandler(async (req, res) => {
      const file = req.file;
      if (!file?.path) {
        sendJson(res, 400, { error: "invalid_request" });
        return;
      }

      const before = new Set((await listInstalledLibraries()).map((l) => l.ubername));
      try {
        // Install libraries from a package *without* requiring `h5p.json` / `content/*`.
        // This enables admin-managed "library-only" packages as well as full
        // exports that embed the library folders at the ZIP root.
        await h5pEditor.uploadPackage(file.path, req.user, { onlyInstallLibraries: true });

        const after = await listInstalledLibraries();
        const installed = after
          .map((l) => l.ubername)
          .filter((u) => !before.has(u))
          .sort((a, b) => a.localeCompare(b));
        sendJson(res, 200, { installed }, { Vary: "Origin" });
      } catch (err) {
        if (err?.httpStatusCode) {
          sendJson(
            res,
            err.httpStatusCode,
            { error: err.errorId || "h5p_error" },
            { Vary: "Origin" },
          );
          return;
        }
        sendJson(res, 400, { error: "invalid_package" }, { Vary: "Origin" });
      } finally {
        try {
          await unlink(file.path);
        } catch {
          // ignore cleanup errors
        }
      }
    }),
  );

  app.get("/player", requireDebugHtmlEnabled, requireAdmin, asyncHandler(async (req, res) => {
    const initialContentId =
      typeof req.query.content_id === "string" ? req.query.content_id : "";
    // NOTE: This debug page uses the same webcomponents + model endpoint as the
    // embedded GUSTAV UI. The route itself is admin-only; `/player/model`
    // still enforces student visibility checks (course scope + released tasks).
    sendHtml(
      res,
      200,
      [
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\" />",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        "<title>H5P Player</title>",
        "</head><body>",
        "<h1>H5P Player</h1>",
        "<p class=\"text-muted\">Admin-only debug UI. The real integration lives inside GUSTAV pages.</p>",
        "<div style=\"display:flex;gap:8px;align-items:center;margin:12px 0;flex-wrap:wrap;\">",
        `  <label>Content ID <input id="contentId" value="${String(initialContentId).replace(/\"/g, "&quot;")}" /></label>`,
        "  <label>Course ID (students) <input id=\"courseId\" value=\"\" /></label>",
        "  <button id=\"loadBtn\" type=\"button\">Load</button>",
        "  <span id=\"status\" style=\"margin-left:8px;color:#555\"></span>",
        "</div>",
        "<div id=\"playerRoot\"></div>",
        "<script type=\"module\">",
        "(() => {",
        "  const statusEl = document.getElementById('status');",
        "  const contentEl = document.getElementById('contentId');",
        "  const courseEl = document.getElementById('courseId');",
        "  const root = document.getElementById('playerRoot');",
        "  const setStatus = (msg) => { if (statusEl) statusEl.textContent = msg || ''; };",
        "",
        "  const renderPlayer = async (cid) => {",
        "    if (!cid) { setStatus('Missing content id.'); return; }",
        "    setStatus('Loading webcomponents…');",
        "    const { defineElements } = await import('/h5p/webcomponents/index.js');",
        "    defineElements(['h5p-player']);",
        "",
        "    const player = document.createElement('h5p-player');",
        "    player.setAttribute('content-id', cid);",
        "    player.loadContentCallback = async (contentId, contextId, _ignoredUserId, readOnlyState) => {",
        "      const url = new URL('/h5p/player/model', window.location.origin);",
        "      url.searchParams.set('content_id', contentId);",
        "      const courseId = (courseEl?.value || '').trim();",
        "      if (courseId) url.searchParams.set('course_id', courseId);",
        "      if (contextId) url.searchParams.set('context_id', contextId);",
        "      if (readOnlyState) url.searchParams.set('read_only_state', 'true');",
        "      const r = await fetch(url.toString(), { credentials: 'include' });",
        "      const data = await r.json().catch(() => ({}));",
        "      if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);",
        "      return data;",
        "    };",
        "    player.addEventListener('xAPI', (ev) => {",
        "      // Debug: log statements to console",
        "      console.log('xAPI', ev?.detail?.statement);",
        "    });",
        "",
        "    root.innerHTML = '';",
        "    root.appendChild(player);",
        "    setStatus('Ready.');",
        "  };",
        "",
        "  document.getElementById('loadBtn')?.addEventListener('click', () => {",
        "    renderPlayer((contentEl?.value || '').trim()).catch((e) => setStatus(String(e?.message || e)));",
        "  });",
        "",
        "  const initial = (contentEl?.value || '').trim();",
        "  if (initial) renderPlayer(initial).catch((e) => setStatus(String(e?.message || e)));",
        "})();",
        "</script>",
        "</body></html>",
      ].join("\n"),
      { "Content-Security-Policy": CSP_DEBUG_HTML },
    );
  }));

  app.post(
    "/contents/import",
    requireTeacher,
    requireSameOrigin,
    uploadImport.single("file"),
    asyncHandler(async (req, res) => {
      const file = req.file;
      if (!file?.path) {
        sendJson(res, 400, { error: "invalid_request" });
        return;
      }

      try {
        const result = await h5pEditor.uploadPackage(file.path, req.user);
        if (!result?.metadata || !result?.parameters) {
          sendJson(res, 400, { error: "invalid_package" });
          return;
        }

        const ubername = getMainLibraryUbername(result.metadata);
        if (!ubername) {
          sendJson(res, 400, { error: "invalid_package" });
          return;
        }

        const contentId = await h5pEditor.saveOrUpdateContent(
          undefined,
          result.parameters,
          result.metadata,
          ubername,
          req.user,
        );
        sendJson(res, 201, { content_id: String(contentId) }, { Vary: "Origin" });
      } catch (err) {
        // Make missing library errors actionable for teachers (common for
        // content-only hub exports without `libraries/*`).
        const errorId = err?.errorId;
        const missingLibraries = err?.replacements?.libraries;
        if (errorId === "install-missing-libraries") {
          const help = "Install content-type libraries first via /h5p/libraries/import (teacher-only).";
          const detail = missingLibraries
            ? `Missing H5P libraries: ${missingLibraries}. ${help}`
            : `Missing H5P libraries. ${help}`;
          sendJson(res, 400, { error: "missing_libraries", detail }, { Vary: "Origin" });
          return;
        }
        sendJson(res, 400, { error: "invalid_package" });
      } finally {
        try {
          await unlink(file.path);
        } catch {
          // ignore cleanup errors
        }
      }
    }),
  );

  app.delete("/contents/:contentId", requireTeacher, requireSameOrigin, asyncHandler(async (req, res) => {
    const { contentId } = req.params;
    if (!(await contentStorage.contentExists(contentId))) {
      sendJson(res, 404, { error: "not_found" }, { Vary: "Origin" });
      return;
    }
    try {
      await h5pEditor.deleteContent(contentId, req.user);
      res.status(204);
      for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
      res.setHeader("Cache-Control", "private, no-store");
      res.setHeader("Vary", "Origin");
      res.end();
    } catch (err) {
      if (err?.httpStatusCode) {
        sendJson(res, err.httpStatusCode, { error: err.errorId || "h5p_error" }, { Vary: "Origin" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" }, { Vary: "Origin" });
    }
  }));

  app.get("/contents/:contentId/export", requireTeacher, asyncHandler(async (req, res) => {
    const { contentId } = req.params;
    if (!(await contentStorage.contentExists(contentId))) {
      sendJson(res, 404, { error: "not_found" });
      return;
    }
    res.status(200);
    for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
    res.setHeader("Cache-Control", "private, no-store");
    res.setHeader("Content-Type", "application/zip");
    const safeName = sanitizeHeaderFilename(contentId);
    res.setHeader("Content-Disposition", `attachment; filename="${safeName}.h5p"`);
    await h5pEditor.exportContent(contentId, res, req.user);
  }));

  // POST /ajax is required for player translations; treat unsafe actions as writes.
  app.post("/ajax", maybeParseAjaxFiles, asyncHandler(async (req, res) => {
    const action = req.query.action;
    if (!action || typeof action !== "string") {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    // CSRF defense-in-depth: `/ajax` is a cookie-authenticated browser POST endpoint.
    // Require same-origin indicators (Origin/Referer) for *all* actions.
    requireSameOrigin(req, res, () => {});
    if (res.headersSent) return;

    // Security: H5P Ajax responses must not be cacheable.
    res.setHeader("Cache-Control", "private, no-store");
    res.setHeader("Vary", "Origin");

    const writeActions = new Set(["files", "library-install", "library-upload", "get-content"]);
    if (writeActions.has(action)) {
      if (!rolesAllowTeacher(req.gustavMe?.roles)) {
        sendJson(res, 403, { error: "forbidden" });
        return;
      }
    }

    const toH5pUpload = (multerFile) => {
      if (!multerFile) return undefined;
      return {
        mimetype: multerFile.mimetype,
        name: multerFile.originalname,
        size: multerFile.size,
        tempFilePath: multerFile.path,
      };
    };

    const filesFile = Array.isArray(req.files?.file) ? toH5pUpload(req.files.file[0]) : undefined;
    const libraryUploadFile = Array.isArray(req.files?.h5p) ? toH5pUpload(req.files.h5p[0]) : undefined;

    try {
      const ajaxBody = normalizeH5PAjaxBody(req.body);
      const result = await h5pAjax.postAjax(
        action,
        ajaxBody,
        req.query.language ?? req.language,
        req.user,
        filesFile,
        req.query.id,
        req.t,
        libraryUploadFile,
        req.query.hubId,
      );
      res.status(200).send(result);
    } catch (err) {
      // Reuse the upstream adapter's error semantics where possible.
      if (err?.httpStatusCode) {
        res.status(err.httpStatusCode).send({ error: err.errorId || "h5p_error" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    } finally {
      // Best-effort cleanup of uploaded temp files
      const cleanup = [];
      if (filesFile?.tempFilePath) cleanup.push(unlink(filesFile.tempFilePath));
      if (libraryUploadFile?.tempFilePath) cleanup.push(unlink(libraryUploadFile.tempFilePath));
      await Promise.allSettled(cleanup);
    }
  }));

  // H5P "finished" reporting: called by the H5P client when a user completed a run.
  //
  // Why we override:
  // - Lumi's default router persists finished data for "resume" and basic stats.
  // - GUSTAV's Teacher Live-Matrix reads progress from `learning_submissions`,
  //   which must be written even when browser xAPI events do not fire reliably.
  //
  // Security:
  // - Requires a valid `gustav_session` cookie (handled by requireAuth).
  // - Enforces strict same-origin (Origin/Referer) to reduce CSRF surface.
  //
  // Note: We implement this route *before* mounting Lumi's ajax router so it
  // takes precedence over the default FinishedDataExpressRouter.
  app.post("/finishedData", asyncHandler(async (req, res) => {
    requireSameOrigin(req, res, () => {});
    if (res.headersSent) return;

    const body = req.body || {};
    const contentId = body.contentId;
    const score = body.score;
    const maxScore = body.maxScore;
    const opened = body.opened;
    const finished = body.finished;
    const time = body.time;
    if (contentId === undefined || score === undefined || maxScore === undefined) {
      sendJson(res, 400, { error: "invalid_request" }, { Vary: "Origin" });
      return;
    }

    try {
      // 1) Persist finished state in the H5P storage backend (resume + stats).
      await h5pEditor.contentUserDataManager.setFinished(
        contentId,
        score,
        maxScore,
        opened,
        finished,
        time,
        req.user,
      );
    } catch (err) {
      if (err?.httpStatusCode) {
        sendJson(res, err.httpStatusCode, { error: err.errorId || "h5p_error" }, { Vary: "Origin" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" }, { Vary: "Origin" });
      return;
    }

    // 2) Persist a Learning submission so Teacher dashboards can read progress.
    const courseId = typeof req.query.course_id === "string" ? req.query.course_id : "";
    const taskId = typeof req.query.task_id === "string" ? req.query.task_id : "";
    if (courseId && taskId) {
      try {
        const rawNum = Number(score);
        const maxNum = Number(maxScore);
        if (Number.isFinite(rawNum) && Number.isFinite(maxNum)) {
          const scoreRaw = Math.max(0, Math.trunc(rawNum));
          const scoreMax = Math.max(0, Math.trunc(maxNum));
          if (scoreRaw <= scoreMax) {
            const cookieHeader = req.get("cookie") || "";
            const originInfo = parseOriginForForwarding(req);
            const idem = buildFinishedSubmissionIdempotencyKey({
              userId: req.user?.id,
              courseId,
              taskId,
              contentId,
              opened,
              finished,
              score: scoreRaw,
              maxScore: scoreMax,
            });

            const base = gustavWebInternalBase.replace(/\/+$/, "");
            const url = `${base}/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`;

            const sessionCookieHeader = buildSessionCookieHeader(cookieHeader, sessionCookieName);
            const frontendCookieHeader = buildSessionCookieHeader(cookieHeader, frontendSessionCookieName);

            let result;
            if (sessionCookieHeader) {
              const headers = {
                "content-type": "application/json",
                "idempotency-key": idem,
                ...(originInfo
                  ? {
                      origin: originInfo.origin,
                      "x-forwarded-proto": originInfo.scheme,
                      "x-forwarded-host": originInfo.host,
                      "x-forwarded-port": originInfo.port,
                    }
                  : {}),
                cookie: sessionCookieHeader,
              };

              result = await forwardLearningSubmission({
                url,
                headers,
                body: JSON.stringify({ kind: "h5p", score_raw: scoreRaw, score_max: scoreMax }),
                timeoutMs: upstreamFetchTimeoutMs,
                maxAttempts: 2,
                baseBackoffMs: 100,
                metrics: finishedForwardingMetrics,
              });
            } else if (frontendCookieHeader) {
              const frontendUrl =
                `${gustavFrontendInternalBase.replace(/\/+$/, "")}/internal/h5p/submissions?course_id=${encodeURIComponent(courseId)}&task_id=${encodeURIComponent(taskId)}`;
              result = await forwardLearningSubmission({
                url: frontendUrl,
                headers: {
                  "content-type": "application/json",
                  "idempotency-key": idem,
                  cookie: frontendCookieHeader,
                },
                body: JSON.stringify({ kind: "h5p", score_raw: scoreRaw, score_max: scoreMax }),
                timeoutMs: upstreamFetchTimeoutMs,
                maxAttempts: 2,
                baseBackoffMs: 100,
                metrics: finishedForwardingMetrics,
              });
            } else {
              result = { ok: false, status: 401, attempts: 1 };
            }
            if (!result.ok) {
              const reason = result.status ? `status=${result.status}` : `error=${result.error || "unknown"}`;
              // eslint-disable-next-line no-console
              console.warn(
                `h5p finishedData → learning submission failed: ${reason} attempts=${result.attempts} failures_total=${finishedForwardingMetrics.failureTotal}`,
              );
            }
          }
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`h5p finishedData → learning submission exception: ${String(err?.name || "error")}`);
      }
    }

    // Match upstream semantics: a successful Ajax response is `{ success: true }`.
    sendJson(res, 200, { success: true }, { Vary: "Origin" });
  }));

  // Mount the Lumi Express router for all read endpoints (libraries/content/params/core/userdata/finished).
  // We disable:
  // - POST /ajax: implemented above with role + CSRF checks
  // - GET /download: we expose export under `/contents/:id/export` (teacher-only)
  // - editor core files: served under /editor-assets (see config.editorLibraryUrl)
  const ajaxRouter = h5pAjaxExpressRouter(
    h5pEditor,
    path.join("/app", "vendor", "h5p", "core"),
    path.join("/app", "vendor", "h5p", "editor"),
    { routePostAjax: false, routeGetDownload: false, routeEditorCoreFiles: true },
    "en",
  );
  app.use(ajaxRouter);

  // Central error handler (defense-in-depth).
  app.use((err, req, res, _next) => {
    // Avoid logging request context (PII). Keep this minimal.
    const msg =
      err && typeof err === "object" && "message" in err ? String(err.message || "") : String(err || "");
    // eslint-disable-next-line no-console
    console.error(`h5p-service unhandled error: ${msg}`);
    if (res.headersSent) return;
    sendJson(res, 500, { error: "internal_error" });
  });

  app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`gustav-h5p listening on :${port} (web=${gustavWebInternalBase})`);
  });
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
