/** Register player routes after global authentication and review-mode guards.
 * Dependencies are supplied by startup; importing this module does not start a service.
 * Existing role, CSRF, storage and response semantics are preserved.
 */
import { checkLearningH5PContentAccess as defaultContentAccess } from "../lib/auth_forwarding.mjs";
import { parseCookies } from "../lib/cookies.mjs";
import { ensureDivEmbedTypes, ensureThemeStylesLast } from "../lib/model_helpers.mjs";
import { rolesAllowTeacher } from "../lib/internal_auth.mjs";
import { parseReviewToken, reviewCookieName, reviewHandleFromToken, reviewTokenFromAuthorizationHeader } from "../lib/review_tokens.mjs";
import { sendHtml, sendJson } from "../lib/response_helpers.mjs";
import { CSP_DEBUG_HTML } from "../lib/security_headers.mjs";
import { pruneCacheToMaxEntries, requireTeacher, requireAdmin } from "../lib/runtime_guards.mjs";
import { asyncHandler } from "../lib/route_helpers.mjs";

export function mountPlayerRoutes(app, {
  h5pPlayer, requireDebugHtmlEnabled, reviewTokenSecret, sessionCookieName, h5pContentAccessCache, authCacheTtlSeconds, H5P_AUTH_CACHE_MAX_ENTRIES, authForwardingOptions, checkLearningH5PContentAccess = defaultContentAccess,
}) {
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
    const taskId =
      typeof req.query.task_id === "string" ? req.query.task_id : contextId;
    const practiceSessionId =
      typeof req.query.practice_session_id === "string" ? req.query.practice_session_id : undefined;
    const practiceItemId =
      typeof req.query.practice_item_id === "string" ? req.query.practice_item_id : undefined;
    const practiceCompletionToken =
      typeof req.query.practice_completion_token === "string" ? req.query.practice_completion_token : undefined;
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
        cookies[sessionCookieName] || "";
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
        const checked = await checkLearningH5PContentAccess(courseId, contentId, cookieHeader, authForwardingOptions);
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
      if (courseId && taskId && out?.integration?.ajax?.setFinished) {
        try {
          const base = "http://local.invalid";
          const u = new URL(String(out.integration.ajax.setFinished), base);
          u.searchParams.set("course_id", String(courseId));
          u.searchParams.set("task_id", String(taskId));
          if (practiceSessionId && practiceItemId && practiceCompletionToken) {
            u.searchParams.set("practice_session_id", practiceSessionId);
            u.searchParams.set("practice_item_id", practiceItemId);
            u.searchParams.set("practice_completion_token", practiceCompletionToken);
          }
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
    const reviewToken = reviewTokenFromAuthorizationHeader(req.get("authorization"));

    if (!contentId || !contextId || !reviewToken) {
      sendJson(res, 400, { error: "invalid_request" });
      return;
    }

    const payload = parseReviewToken(reviewToken, { secret: reviewTokenSecret });
    if (!payload) {
      sendJson(res, 403, { error: "forbidden" });
      return;
    }
    const reviewHandle = reviewHandleFromToken(reviewToken);
    const cookieName = reviewCookieName(reviewHandle);
    if (!reviewHandle || !cookieName) {
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

      // Mark subsequent userState reads as review-mode requests. The encrypted
      // credential itself stays in an HttpOnly cookie and never enters the URL.
      if (out?.integration?.ajax?.contentUserData) {
        try {
          const base = "http://local.invalid";
          const u = new URL(String(out.integration.ajax.contentUserData), base);
          u.searchParams.delete("review_token");
          u.searchParams.set("review_mode", "true");
          u.searchParams.set("review_id", reviewHandle);
          u.searchParams.set("contextId", String(contextId));
          out.integration.ajax.contentUserData = `${u.pathname}${u.search || ""}`;
        } catch {
          // Do not fail model loading when URL parsing fails.
        }
      }

      const nowSeconds = Math.floor(Date.now() / 1000);
      const maxAgeSeconds = Math.max(1, Math.min(10 * 60, Math.floor(payload.exp) - nowSeconds));
      res.cookie(cookieName, reviewToken, {
        httpOnly: true,
        secure: true,
        sameSite: "strict",
        path: "/h5p",
        maxAge: maxAgeSeconds * 1000,
      });
      sendJson(res, 200, out, { "Referrer-Policy": "no-referrer" });
    } catch (err) {
      if (err?.httpStatusCode === 404) {
        sendJson(res, 404, { error: "not_found" });
        return;
      }
      sendJson(res, 500, { error: "internal_error" });
    }
  }));

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
}
