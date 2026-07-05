import { createHmac, timingSafeEqual } from "node:crypto";


export function parseReviewToken(token, { secret, nowSeconds = Math.floor(Date.now() / 1000) } = {}) {
  const reviewTokenSecret = String(secret || "").trim();
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
  if (exp <= Number(nowSeconds)) return null;

  return { teacherSub, studentSub, courseId, taskId, contentId, exp };
}
