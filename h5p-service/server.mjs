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
import { access, readdir, writeFile } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import express from "express";
import multer from "multer";
import { debugPagesEnabled, isProdLikeEnv } from "./lib/env.mjs";
import { createFinishedForwardingMetrics } from "./lib/finished_forwarding.mjs";
import { createReviewModeMiddleware } from "./lib/review_mode_middleware.mjs";
import { sendHtml, sendJson } from "./lib/response_helpers.mjs";
import { mountPublicStaticAssets } from "./lib/public_assets.mjs";
import { applySecurityHeaders } from "./lib/security_headers.mjs";
import {
  buildStorageDirs,
  probeStorageDirs,
} from "./lib/storage_helpers.mjs";
import {
  createRequireAuth,
  parseMaxEntries,
  requireStudentOrTeacher,
} from "./lib/runtime_guards.mjs";

import { asyncHandler } from "./lib/route_helpers.mjs";
import { mountAuthoringRoutes } from "./routes/authoring.mjs";
import { mountPlayerRoutes } from "./routes/player.mjs";
import { mountAjaxRoutes } from "./routes/ajax.mjs";

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
const reviewTokenSecret = String(process.env.H5P_REVIEW_TOKEN_SECRET || "").trim();
const h5pInternalSharedSecret = String(process.env.H5P_INTERNAL_SHARED_SECRET || "").trim();
const gustavEnv = String(process.env.GUSTAV_ENV || "dev").trim().toLowerCase();
const isProdLike = isProdLikeEnv(gustavEnv);
const upstreamFetchTimeoutMsRaw = Number.parseInt(process.env.H5P_UPSTREAM_FETCH_TIMEOUT_MS || "5000", 10);
const upstreamFetchTimeoutMs =
  Number.isFinite(upstreamFetchTimeoutMsRaw) && upstreamFetchTimeoutMsRaw > 0 ? upstreamFetchTimeoutMsRaw : 5000;
const authForwardingOptions = {
  gustavWebInternalBase,
  gustavFrontendInternalBase,
  sessionCookieName,
  frontendSessionCookieName,
  timeoutMs: upstreamFetchTimeoutMs,
};
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

const storageDirs = buildStorageDirs(storageRoot);

/**
 * Cache auth lookups for short bursts (editor/player loads many assets quickly).
 * Key: session id. Value: { expiresAtMs, payload }
 */
const authCache = new Map();
const requireAuth = createRequireAuth({
  h5pInternalSharedSecret,
  sessionCookieName,
  frontendSessionCookieName,
  authCacheTtlSeconds,
  authCacheMaxEntries: AUTH_CACHE_MAX_ENTRIES,
  authForwardingOptions,
  authCache,
});

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

function requireDebugHtmlEnabled(_req, res, next) {
  if (debugHtmlEnabled) return next();
  sendHtml(res, 404, "");
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

  const storage = await probeStorageDirs(storageDirs);
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
    applySecurityHeaders(res);
    next();
  });

  // Body parsing for H5P Ajax endpoints (user state / finished data).
  app.use(express.json({ limit: "2mb" }));
  app.use(express.urlencoded({ extended: false, limit: "2mb" }));

  // Public readiness probe (used by E2E and docker-compose health checks).
  app.get("/healthz", asyncHandler(async (_req, res) => {
    const storage = await probeStorageDirs(storageDirs);
    sendJson(res, storage.ok ? 200 : 503, {
      status: storage.ok ? "healthy" : "unhealthy",
      service: "gustav-h5p",
      time: new Date().toISOString(),
      // Keep the public payload minimal (no filesystem paths, no raw errors).
      storage: { ok: storage.ok },
    });
  }));

  mountPublicStaticAssets(app);

  // Everything else is authenticated.
  app.use(requireAuth);
  app.use(requireStudentOrTeacher);

  app.use(createReviewModeMiddleware({ reviewTokenSecret }));

  app.get("/auth/me", (req, res) => {
    sendJson(res, 200, req.gustavMe);
  });

  mountAuthoringRoutes(app, {
    h5pEditor, contentStorage, storageDirs, listInstalledLibraries, uploadImport, requireDebugHtmlEnabled,
  });

  mountPlayerRoutes(app, {
    h5pPlayer, requireDebugHtmlEnabled, reviewTokenSecret, sessionCookieName, frontendSessionCookieName, h5pContentAccessCache, authCacheTtlSeconds, H5P_AUTH_CACHE_MAX_ENTRIES, authForwardingOptions,
  });

  mountAjaxRoutes(app, {
    h5pAjax, h5pEditor, maybeParseAjaxFiles, h5pAjaxExpressRouter, sessionCookieName, frontendSessionCookieName, gustavWebInternalBase, gustavFrontendInternalBase, upstreamFetchTimeoutMs, finishedForwardingMetrics,
  });

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
