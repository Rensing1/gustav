import { createHmac, timingSafeEqual } from "node:crypto";

import { env } from "$env/dynamic/private";
import type { Cookies } from "@sveltejs/kit";

export const COURSE_INVITE_INTENT_COOKIE = "gustav_course_invite_intent";

export type CourseInviteIntent = {
  token: string;
  accepted: boolean;
  expiresAt: number;
};

function signature(payload: string, secret: string): string {
  if (Buffer.byteLength(secret || "", "utf8") < 32 || secret.startsWith("CHANGE_ME")) {
    throw new Error("frontend_session_secret_invalid");
  }
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function serializeCourseInviteIntent(intent: CourseInviteIntent, secret: string): string {
  const payload = Buffer.from(JSON.stringify(intent), "utf8").toString("base64url");
  return `${payload}.${signature(payload, secret)}`;
}

export function parseCourseInviteIntent(
  value: string | undefined,
  secret: string,
  nowSeconds = Math.floor(Date.now() / 1000)
): CourseInviteIntent | null {
  if (!value) return null;
  const [payload, supplied] = value.split(".", 2);
  if (!payload || !supplied) return null;
  const expected = signature(payload, secret);
  try {
    if (!timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) return null;
  } catch {
    return null;
  }
  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as Partial<CourseInviteIntent>;
    if (
      typeof parsed.token !== "string"
      || parsed.token.length < 20
      || parsed.token.length > 512
      || typeof parsed.accepted !== "boolean"
      || typeof parsed.expiresAt !== "number"
      || parsed.expiresAt <= nowSeconds
    ) {
      return null;
    }
    return { token: parsed.token, accepted: parsed.accepted, expiresAt: parsed.expiresAt };
  } catch {
    return null;
  }
}

function secret(): string {
  return env.FRONTEND_SESSION_SECRET || "";
}

function secureCookie(): boolean {
  return (env.WEB_BASE || env.ORIGIN || "").startsWith("https://")
    || env.NODE_ENV === "production";
}

export function setCourseInviteIntent(cookies: Cookies, intent: CourseInviteIntent): void {
  const maxAge = Math.max(1, Math.min(86_400, intent.expiresAt - Math.floor(Date.now() / 1000)));
  cookies.set(COURSE_INVITE_INTENT_COOKIE, serializeCourseInviteIntent(intent, secret()), {
    path: "/invite",
    httpOnly: true,
    secure: secureCookie(),
    sameSite: "lax",
    maxAge
  });
}

export function readCourseInviteIntent(cookies: Cookies): CourseInviteIntent | null {
  return parseCourseInviteIntent(cookies.get(COURSE_INVITE_INTENT_COOKIE), secret());
}

export function clearCourseInviteIntent(cookies: Cookies): void {
  cookies.delete(COURSE_INVITE_INTENT_COOKIE, {
    path: "/invite",
    httpOnly: true,
    secure: secureCookie(),
    sameSite: "lax"
  });
}
