import { createDecipheriv, createHash } from "node:crypto";


const REVIEW_CREDENTIAL_AAD = Buffer.from("gustav-h5p-review-v1", "utf-8");
export const REVIEW_COOKIE_NAME = "__Secure-gustav_h5p_review";


export function reviewTokenFromAuthorizationHeader(value) {
  const match = /^Bearer\s+(.+)$/i.exec(String(value || "").trim());
  const credential = match?.[1]?.trim();
  return credential || null;
}


export function parseReviewToken(token, { secret, nowSeconds = Math.floor(Date.now() / 1000) } = {}) {
  const reviewTokenSecret = String(secret || "").trim();
  if (!reviewTokenSecret) return null;
  if (typeof token !== "string" || !token) return null;

  const parts = token.split(".");
  if (parts.length !== 3 || parts[0] !== "v1") return null;
  const [, nonceB64, ciphertextB64] = parts;
  let nonce;
  let encrypted;
  try {
    nonce = Buffer.from(nonceB64, "base64url");
    encrypted = Buffer.from(ciphertextB64, "base64url");
  } catch {
    return null;
  }
  if (nonce.length !== 12 || encrypted.length <= 16) return null;

  let payloadBytes;
  try {
    const key = createHash("sha256").update(reviewTokenSecret, "utf-8").digest();
    const ciphertext = encrypted.subarray(0, encrypted.length - 16);
    const authTag = encrypted.subarray(encrypted.length - 16);
    const decipher = createDecipheriv("aes-256-gcm", key, nonce);
    decipher.setAAD(REVIEW_CREDENTIAL_AAD);
    decipher.setAuthTag(authTag);
    payloadBytes = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
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
  const taskId = obj.task_id;
  const contentId = obj.content_id;
  const exp = obj.exp;

  if (typeof teacherSub !== "string" || !teacherSub) return null;
  if (typeof studentSub !== "string" || !studentSub) return null;
  if (typeof taskId !== "string" || !taskId) return null;
  if (typeof contentId !== "string" || !contentId) return null;
  if (typeof exp !== "number" || !Number.isFinite(exp)) return null;
  if (exp <= Number(nowSeconds)) return null;

  return { teacherSub, studentSub, taskId, contentId, exp };
}
