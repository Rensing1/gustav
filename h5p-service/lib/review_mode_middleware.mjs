import { rolesAllowTeacher } from "./internal_auth.mjs";
import { parseCookies } from "./cookies.mjs";
import { sendJson } from "./response_helpers.mjs";
import {
  parseReviewToken,
  reviewCookieName,
  reviewHandleFromToken,
} from "./review_tokens.mjs";


export function createReviewModeMiddleware({
  reviewTokenSecret,
  parseReviewTokenImpl = parseReviewToken,
  rolesAllowTeacherImpl = rolesAllowTeacher,
  sendJsonImpl = sendJson,
} = {}) {
  return function reviewModeMiddleware(req, res, next) {
    const reviewMode = req.query.review_mode === "true";
    if (!reviewMode) {
      next();
      return;
    }

    // Defense-in-depth: review is teacher-only.
    if (!rolesAllowTeacherImpl(req.gustavMe?.roles)) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }

    // The URL carries only a random selector. The credential remains in the
    // matching HttpOnly cookie and never enters browser-visible URLs.
    const reviewHandle = typeof req.query.review_id === "string" ? req.query.review_id : "";
    const cookieName = reviewCookieName(reviewHandle);
    if (!cookieName) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }
    const cookieHeader = typeof req.get === "function" ? req.get("cookie") || "" : "";
    const reviewToken = parseCookies(cookieHeader)[cookieName];
    if (reviewHandleFromToken(reviewToken) !== reviewHandle) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }
    const payload = parseReviewTokenImpl(reviewToken, { secret: reviewTokenSecret });
    if (!payload) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }
    if (payload.teacherSub !== req.user?.id) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }

    // Strict read-only: block all non-GET requests when a review token is present.
    if (req.method !== "GET") {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }

    // Fail-closed: only allow the token to be used for content user data reads.
    const match = req.path.match(/\/contentUserData\/([^/]+)/);
    const contentIdFromPath = match?.[1] ? String(match[1]) : "";
    if (!contentIdFromPath) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }
    if (contentIdFromPath !== payload.contentId) {
      sendJsonImpl(res, 403, { error: "forbidden" });
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
      sendJsonImpl(res, 403, { error: "forbidden" });
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
  };
}
