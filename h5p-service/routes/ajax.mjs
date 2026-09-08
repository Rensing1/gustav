/** Register ajax routes after global authentication and review-mode guards.
 * Dependencies are supplied by startup; importing this module does not start a service.
 * Existing role, CSRF, storage and response semantics are preserved.
 */
import path from "node:path";
import { unlink } from "node:fs/promises";
import { normalizeH5PAjaxBody } from "../lib/ajax_body.mjs";
import { buildSessionCookieHeader } from "../lib/cookies.mjs";
import { forwardLearningSubmission } from "../lib/finished_forwarding.mjs";
import { buildFinishedSubmissionIdempotencyKey, parseOriginForForwarding } from "../lib/finished_submission_context.mjs";
import { rolesAllowTeacher } from "../lib/internal_auth.mjs";
import { sendJson } from "../lib/response_helpers.mjs";
import { requireSameOrigin } from "../lib/runtime_guards.mjs";
import { asyncHandler } from "../lib/route_helpers.mjs";

export function mountAjaxRoutes(app, {
  h5pAjax, h5pEditor, maybeParseAjaxFiles, h5pAjaxExpressRouter, sessionCookieName, frontendSessionCookieName, gustavWebInternalBase, gustavFrontendInternalBase, upstreamFetchTimeoutMs, finishedForwardingMetrics,
}) {
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
    const practiceSessionId = typeof req.query.practice_session_id === "string" ? req.query.practice_session_id : "";
    const practiceItemId = typeof req.query.practice_item_id === "string" ? req.query.practice_item_id : "";
    const practiceCompletionToken = typeof req.query.practice_completion_token === "string" ? req.query.practice_completion_token : "";
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

            const isPractice = Boolean(practiceSessionId && practiceItemId && practiceCompletionToken);
            const base = gustavWebInternalBase.replace(/\/+$/, "");
            const url = isPractice
              ? `${base}/api/learning/practice/sessions/${encodeURIComponent(practiceSessionId)}/items/${encodeURIComponent(practiceItemId)}/attempts`
              : `${base}/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`;
            const submissionBody = isPractice
              ? { score_raw: scoreRaw, score_max: scoreMax, practice_completion_token: practiceCompletionToken }
              : { kind: "h5p", score_raw: scoreRaw, score_max: scoreMax };

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
                body: JSON.stringify(submissionBody),
                timeoutMs: upstreamFetchTimeoutMs,
                maxAttempts: 2,
                baseBackoffMs: 100,
                metrics: finishedForwardingMetrics,
              });
            } else if (frontendCookieHeader) {
              const frontendUrl = isPractice
                ? `${gustavFrontendInternalBase.replace(/\/+$/, "")}/internal/h5p/practice-attempts?session_id=${encodeURIComponent(practiceSessionId)}&item_id=${encodeURIComponent(practiceItemId)}`
                : `${gustavFrontendInternalBase.replace(/\/+$/, "")}/internal/h5p/submissions?course_id=${encodeURIComponent(courseId)}&task_id=${encodeURIComponent(taskId)}`;
              result = await forwardLearningSubmission({
                url: frontendUrl,
                headers: {
                  "content-type": "application/json",
                  "idempotency-key": idem,
                  cookie: frontendCookieHeader,
                },
                body: JSON.stringify(submissionBody),
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
}
