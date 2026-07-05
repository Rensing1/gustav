import { createHash } from "node:crypto";


export function parseOriginForForwarding(req) {
  // The Learning API enforces strict same-origin CSRF checks. Reusing the
  // browser-provided Origin/Referer preserves local = prod behavior.
  const origin = req.get("origin") || "";
  if (origin) {
    try {
      const u = new URL(origin);
      const scheme = String(u.protocol || "").replace(/:$/, "").toLowerCase() || "http";
      const host = String(u.hostname || "").toLowerCase();
      const port = u.port ? String(u.port) : scheme === "https" ? "443" : "80";
      if (host) return { origin: `${scheme}://${u.host}`, scheme, host, port };
    } catch {
      // Fall back to Referer parsing below (e.g., Origin: null in sandboxed iframes).
    }
  }

  const referer = req.get("referer") || "";
  if (referer) {
    try {
      const u = new URL(referer);
      const scheme = String(u.protocol || "").replace(/:$/, "").toLowerCase() || "http";
      const host = String(u.hostname || "").toLowerCase();
      const port = u.port ? String(u.port) : scheme === "https" ? "443" : "80";
      if (!host) return null;
      return { origin: `${scheme}://${u.host}`, scheme, host, port };
    } catch {
      return null;
    }
  }

  return null;
}


export function buildFinishedSubmissionIdempotencyKey({
  userId,
  courseId,
  taskId,
  contentId,
  opened,
  finished,
  score,
  maxScore,
}) {
  const raw = [
    "h5p_finished_v1",
    String(userId || ""),
    String(courseId || ""),
    String(taskId || ""),
    String(contentId || ""),
    String(opened || ""),
    String(finished || ""),
    String(score || ""),
    String(maxScore || ""),
  ].join("|");
  const digest = createHash("sha256").update(raw, "utf8").digest("hex");
  // Must satisfy Learning API: [A-Za-z0-9_-]{1,64}
  return `h5pf_${digest.slice(0, 56)}`;
}
