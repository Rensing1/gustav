import { createHash } from "node:crypto";


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
