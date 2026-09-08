/** Register authoring routes after global authentication and review-mode guards.
 * Dependencies are supplied by startup; importing this module does not start a service.
 * Existing role, CSRF, storage and response semantics are preserved.
 */
import { unlink } from "node:fs/promises";
import { sendHtml, sendJson } from "../lib/response_helpers.mjs";
import { applySecurityHeaders, CSP_DEBUG_HTML } from "../lib/security_headers.mjs";
import { probeStorageDirs, sanitizeHeaderFilename } from "../lib/storage_helpers.mjs";
import { ensureThemeStylesLast } from "../lib/model_helpers.mjs";
import { requireAdmin, requireTeacher, requireSameOrigin } from "../lib/runtime_guards.mjs";
import { asyncHandler, getMainLibraryUbername } from "../lib/route_helpers.mjs";

export function mountAuthoringRoutes(app, {
  h5pEditor, contentStorage, storageDirs, listInstalledLibraries, uploadImport, requireDebugHtmlEnabled,
}) {
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
    const storage = await probeStorageDirs(storageDirs);
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
      applySecurityHeaders(res);
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
    applySecurityHeaders(res);
    res.setHeader("Cache-Control", "private, no-store");
    res.setHeader("Content-Type", "application/zip");
    const safeName = sanitizeHeaderFilename(contentId);
    res.setHeader("Content-Disposition", `attachment; filename="${safeName}.h5p"`);
    await h5pEditor.exportContent(contentId, res, req.user);
  }));
}
