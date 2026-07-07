import { rolesAllowTeacher } from "./internal_auth.mjs";
import { sendJson } from "./response_helpers.mjs";
import { parseReviewToken } from "./review_tokens.mjs";


export function createReviewModeMiddleware({
  reviewTokenSecret,
  parseReviewTokenImpl = parseReviewToken,
  rolesAllowTeacherImpl = rolesAllowTeacher,
  sendJsonImpl = sendJson,
} = {}) {
  return function reviewModeMiddleware(req, res, next) {
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
    if (!rolesAllowTeacherImpl(req.gustavMe?.roles)) {
      sendJsonImpl(res, 403, { error: "forbidden" });
      return;
    }

    // Review token must be valid and match the authenticated teacher.
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
