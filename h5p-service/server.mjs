/**
 * GUSTAV H5P Service (Phase 1 – Lumi PoC)
 *
 * Why:
 *   Provide a dedicated H5P runtime under `/h5p/*` while keeping authentication
 *   based on the existing `gustav_session` cookie (no extra browser tokens).
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
 *   - `GET /player?content_id=...` (student/teacher/admin) renders the H5P player.
 *   - `GET /editor` (teacher/admin) is a minimal Phase-1 UI (import form).
 *
 * Security notes:
 *   - "Fail closed": if auth cannot be proven, respond 401/403.
 *   - CSP is intentionally permissive for `/h5p` (per current decision),
 *     but still scoped to this service only (route-level separation via proxy).
 *   - Trusted-content model: H5P packages are treated as executable code.
 *     Only role `teacher` (and `admin`) may import/export packages.
 *   - Write routes require strict same-origin checks via Origin/Referer.
 */

import path from "node:path";
import { access, mkdir, readdir, unlink, writeFile } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import express from "express";
import multer from "multer";

const port = Number.parseInt(process.env.PORT || "3000", 10);
const gustavWebInternalBase = process.env.GUSTAV_WEB_INTERNAL_BASE || "http://web:8000";
const sessionCookieName = process.env.SESSION_COOKIE_NAME || "gustav_session";
const authCacheTtlSeconds = Number.parseInt(process.env.AUTH_CACHE_TTL_SECONDS || "30", 10);
const storageRoot = process.env.H5P_STORAGE_ROOT || "/data/h5p";
const uploadMaxBytes = Number.parseInt(
  process.env.H5P_MAX_UPLOAD_BYTES || String(512 * 1024 * 1024),
  10,
);

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

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  // Needed so browser form submits include a same-origin Referer header.
  // We still avoid leaking Referer cross-origin.
  "Referrer-Policy": "same-origin",
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

function sendJson(res, statusCode, body, headers = {}) {
  res.status(statusCode);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
  res.setHeader("Cache-Control", "no-store");
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  res.json(body);
}

function sendHtml(res, statusCode, html, headers = {}) {
  res.status(statusCode);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
  res.setHeader("Cache-Control", "no-store");
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  res.type("html").send(html);
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

function getPublicOrigin(req) {
  const proto = (req.get("x-forwarded-proto") || req.protocol || "").split(",")[0].trim();
  const host = (req.get("x-forwarded-host") || req.get("host") || "").split(",")[0].trim();
  if (!proto || !host) return null;
  return `${proto}://${host}`;
}

function requireSameOrigin(req, res, next) {
  const expected = getPublicOrigin(req);
  const origin = req.get("origin");
  const referer = req.get("referer");

  if (!expected) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }

  const originOk = origin ? origin === expected : true;
  let refererOk = true;
  if (referer) {
    try {
      const parsed = new URL(referer);
      refererOk = `${parsed.protocol}//${parsed.host}` === expected;
    } catch {
      refererOk = false;
    }
  }

  // Require at least one same-origin indicator for browser write requests.
  if (!origin && !referer) {
    sendJson(res, 403, { error: "csrf_violation" }, { Vary: "Origin" });
    return;
  }
  if (!originOk || !refererOk) {
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
  const url = `${gustavWebInternalBase.replace(/\/+$/, "")}/api/me`;
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

async function requireAuth(req, res, next) {
  const cookieHeader = req.get("cookie") || "";
  const cookies = parseCookies(cookieHeader);
  const sid = cookies[sessionCookieName];
  if (!sid) {
    sendJson(res, 401, { error: "unauthenticated" });
    return;
  }

  const cached = authCache.get(sid);
  const now = Date.now();
  if (cached && cached.expiresAtMs > now) {
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

  try {
    const me = await fetchGustavMe(cookieHeader);
    if (!me.ok) {
      sendJson(res, me.status === 401 ? 401 : 502, { error: "unauthenticated" });
      return;
    }
    authCache.set(sid, { expiresAtMs: now + authCacheTtlSeconds * 1000, payload: me.payload });
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

  const app = express();
  app.disable("x-powered-by");
  app.set("trust proxy", true);

  // Security headers for all responses (Cache-Control is set route-specific).
  app.use((req, res, next) => {
    for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
    next();
  });

  // Body parsing for H5P Ajax endpoints (user state / finished data).
  app.use(express.json({ limit: "2mb" }));
  app.use(express.urlencoded({ extended: false, limit: "2mb" }));

  // Public readiness probe (used by E2E and docker-compose health checks).
  app.get("/healthz", async (_req, res) => {
    const storage = await probeStorage();
    sendJson(res, storage.ok ? 200 : 503, {
      status: storage.ok ? "healthy" : "unhealthy",
      service: "gustav-h5p",
      time: new Date().toISOString(),
      storage,
    });
  });

  // Everything else is authenticated.
  app.use(requireAuth);
  app.use(requireStudentOrTeacher);

  // Serve Lumi web components (ES modules).
  app.use(
    "/webcomponents",
    express.static(
      path.join("/app", "node_modules", "@lumieducation", "h5p-webcomponents", "build", "es2015"),
      // Note: Lumi's ES2015 build uses extensionless relative imports like
      // `import ... from './h5p-editor'`. Browsers do not auto-append `.js`,
      // so we enable a `.js` fallback to make those imports resolve.
      { cacheControl: true, etag: true, lastModified: true, maxAge: 31536000000, extensions: ["js"] },
    ),
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
      maxAge: 31536000000,
    }),
  );

  app.get("/auth/me", (req, res) => {
    sendJson(res, 200, req.gustavMe);
  });

  app.get("/editor", requireTeacher, (_req, res) => {
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
        "<p class=\"muted\">Trusted-content model: only <code>teacher</code>/<code>admin</code> may install libraries and create/update content.</p>",
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
        "<p id=\"status\" class=\"muted\"></p>",
        "<h5p-editor id=\"h5pEditor\" content-id=\"new\"></h5p-editor>",
        "<script type=\"importmap\">",
        JSON.stringify({
          imports: {
            deepmerge: "/h5p/webcomponents/vendor/deepmerge.js",
            "await-lock": "/h5p/webcomponents/vendor/await-lock.js",
          },
        }),
        "</script>",
        "<script type=\"module\">",
        "import { defineElements } from '/h5p/webcomponents/index.js';",
        "defineElements(['h5p-editor']);",
        "",
        "const editor = document.getElementById('h5pEditor');",
        "const status = document.getElementById('status');",
        "const contentIdInput = document.getElementById('contentId');",
        "const setStatus = (msg) => { status.textContent = msg || ''; };",
        "",
        "// Workaround: the Lumi webcomponent deliberately does NOT re-render when switching",
        "// from content-id='new' to an existing id (to avoid flicker when saving new content).",
        "// For our Phase-1 page we *do* want this switch to load existing content, so we force",
        "// an attribute transition via `undefined` first.",
        "const setEditorContentId = (cid) => {",
        "  editor.contentId = undefined;",
        "  editor.contentId = cid;",
        "};",
        "",
        "editor.loadContentCallback = async (contentId) => {",
          "  const url = new URL('/h5p/editor/model', window.location.origin);",
        "  if (contentId) url.searchParams.set('content_id', contentId);",
        "  const r = await fetch(url.toString(), { credentials: 'include' });",
        "  if (!r.ok) {",
        "    let msg = `HTTP ${r.status}`;",
        "    try { const j = await r.json(); msg = j?.error || msg; } catch {}",
        "    throw new Error(msg);",
        "  }",
        "  return await r.json();",
        "};",
        "",
        "editor.saveContentCallback = async (contentId, requestBody) => {",
        "  const isUpdate = Boolean(contentId);",
        "  const url = isUpdate ? `/h5p/contents/${encodeURIComponent(contentId)}` : '/h5p/contents';",
        "  const method = isUpdate ? 'PATCH' : 'POST';",
        "  const r = await fetch(url, {",
        "    method,",
        "    credentials: 'include',",
        "    headers: { 'Content-Type': 'application/json' },",
        "    body: JSON.stringify(requestBody),",
        "  });",
        "  const data = await r.json().catch(() => ({}));",
        "  if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);",
        "  return { contentId: data.content_id, metadata: data.metadata };",
        "};",
        "",
        "document.getElementById('loadNew').addEventListener('click', () => {",
        "  contentIdInput.value = '';",
        "  setEditorContentId('new');",
        "  setStatus('Creating new content…');",
        "});",
        "document.getElementById('loadExisting').addEventListener('click', () => {",
        "  const cid = (contentIdInput.value || '').trim();",
        "  if (!cid) { setStatus('Enter a content id first.'); return; }",
        "  setEditorContentId(cid);",
        "  setStatus(`Loading content ${cid}…`);",
        "});",
        "editor.addEventListener('editorloaded', (ev) => {",
        "  setStatus(`Editor loaded (${ev?.detail?.ubername || 'unknown library'}).`);",
        "});",
        "editor.addEventListener('saved', (ev) => {",
        "  const cid = ev?.detail?.contentId;",
        "  contentIdInput.value = cid || '';",
        "  status.textContent = '';",
        "  if (!cid) { status.textContent = 'Saved.'; return; }",
        "  const code = document.createElement('code');",
        "  code.textContent = cid;",
        "  status.append('Saved content ', code, '. ');",
        "  const a = document.createElement('a');",
        "  a.href = '/h5p/player?content_id=' + encodeURIComponent(cid);",
        "  a.textContent = 'Open player';",
        "  status.append(a);",
        "});",
        "editor.addEventListener('save-error', (ev) => {",
        "  setStatus(`Save error: ${ev?.detail?.message || 'unknown'}`);",
        "});",
        "editor.addEventListener('validation-error', (ev) => {",
        "  setStatus(`Validation error: ${ev?.detail?.message || 'unknown'}`);",
        "});",
        "document.getElementById('save').addEventListener('click', async () => {",
        "  try {",
        "    setStatus('Saving…');",
        "    const saved = await editor.save();",
        "    if (saved?.contentId) contentIdInput.value = saved.contentId;",
        "  } catch (e) {",
        "    setStatus(String(e?.message || e));",
        "  }",
        "});",
        "</script>",
        "</div>",
        "</body></html>",
      ].join(""),
    );
  });

  app.get("/editor/model", requireTeacher, async (req, res) => {
    const contentId =
      typeof req.query.content_id === "string" ? req.query.content_id : undefined;
    if (req.query.content_id !== undefined && !contentId) {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    try {
      const language = typeof req.query.language === "string" ? req.query.language : req.language;
      const model = await h5pEditor.render(contentId, language, req.user);
      const out = { ...model };
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
  });

  app.post("/contents", requireTeacher, requireSameOrigin, async (req, res) => {
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
  });

  app.patch("/contents/:contentId", requireTeacher, requireSameOrigin, async (req, res) => {
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
  });

  app.get("/libraries", requireTeacher, async (_req, res) => {
    const storage = await probeStorage();
    if (!storage.ok) {
      sendJson(res, 503, { error: "storage_unavailable" });
      return;
    }
    const libraries = await listInstalledLibraries();
    sendJson(res, 200, { libraries });
  });

  app.post(
    "/libraries/import",
    requireTeacher,
    requireSameOrigin,
    uploadImport.single("file"),
    async (req, res) => {
      const file = req.file;
      if (!file?.path) {
        sendJson(res, 400, { error: "invalid_request" });
        return;
      }

      const before = new Set((await listInstalledLibraries()).map((l) => l.ubername));
      try {
        await h5pAjax.postAjax(
          "library-upload",
          req.body ?? {},
          req.query.language ?? req.language,
          req.user,
          undefined,
          undefined,
          req.t,
          {
            mimetype: file.mimetype,
            name: file.originalname,
            size: file.size,
            tempFilePath: file.path,
          },
          undefined,
        );
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
    },
  );

  app.get("/player", async (req, res) => {
    const contentId = req.query.content_id;
    if (!contentId || typeof contentId !== "string") {
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
          "<p>Missing query param: <code>content_id</code>.</p>",
          "</body></html>",
        ].join(""),
      );
      return;
    }

    try {
      const snippet = await h5pPlayer.render(contentId, req.user, "en", {
        showDownloadButton: false,
        showEmbedButton: false,
        showCopyButton: false,
      });
      sendHtml(
        res,
        200,
        [
          "<!doctype html>",
          "<html><head><meta charset=\"utf-8\" />",
          "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
          "<title>H5P Player</title>",
          "</head><body>",
          typeof snippet === "string" ? snippet : JSON.stringify(snippet),
          "</body></html>",
        ].join(""),
      );
    } catch (err) {
      if (err?.httpStatusCode === 404) {
        sendJson(res, 404, { error: "not_found" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    }
  });

  app.post(
    "/contents/import",
    requireTeacher,
    requireSameOrigin,
    uploadImport.single("file"),
    async (req, res) => {
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
    },
  );

  app.get("/contents/:contentId/export", requireTeacher, async (req, res) => {
    const { contentId } = req.params;
    if (!(await contentStorage.contentExists(contentId))) {
      sendJson(res, 404, { error: "not_found" });
      return;
    }
    res.status(200);
    for (const [k, v] of Object.entries(SECURITY_HEADERS)) res.setHeader(k, v);
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Content-Type", "application/zip");
    res.setHeader("Content-Disposition", `attachment; filename=${contentId}.h5p`);
    await h5pEditor.exportContent(contentId, res, req.user);
  });

  // POST /ajax is required for player translations; treat unsafe actions as writes.
  app.post("/ajax", maybeParseAjaxFiles, async (req, res) => {
    const action = req.query.action;
    if (!action || typeof action !== "string") {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    const writeActions = new Set(["files", "library-install", "library-upload", "get-content"]);
    if (writeActions.has(action)) {
      if (!rolesAllowTeacher(req.gustavMe?.roles)) {
        sendJson(res, 403, { error: "forbidden" });
        return;
      }
      // Library/content writes must be same-origin.
      requireSameOrigin(req, res, () => {});
      if (res.headersSent) return;
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
      const result = await h5pAjax.postAjax(
        action,
        req.body,
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
  });

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
