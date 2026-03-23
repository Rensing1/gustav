import type { Cookies } from "@sveltejs/kit";

import { env } from "$env/dynamic/private";

export const FRONTEND_SESSION_COOKIE_NAME = "gustav_bff_session";
export const BACKEND_SESSION_COOKIE_NAME = "gustav_session";

function useSecureCookie(): boolean {
  if ((env.ORIGIN || "").startsWith("https://")) {
    return true;
  }
  return (env.NODE_ENV || "").toLowerCase() === "production";
}

export function buildBackendSessionCookieHeader(sessionId: string | null | undefined): string | null {
  if (!sessionId) {
    return null;
  }
  return `${BACKEND_SESSION_COOKIE_NAME}=${sessionId}`;
}

export function buildBackendAuthorizationHeader(sessionId: string | null | undefined): string | null {
  if (!sessionId) {
    return null;
  }
  return `Bearer session:${sessionId}`;
}

export function readFrontendSessionCookie(cookies: Cookies): string | null {
  return cookies.get(FRONTEND_SESSION_COOKIE_NAME) ?? null;
}

export function setFrontendSessionCookie(cookies: Cookies, sessionId: string): void {
  cookies.set(FRONTEND_SESSION_COOKIE_NAME, sessionId, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

export function clearFrontendSessionCookie(cookies: Cookies): void {
  cookies.delete(FRONTEND_SESSION_COOKIE_NAME, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

export function extractBackendSessionId(setCookieHeader: string | null): string | null {
  if (!setCookieHeader) {
    return null;
  }

  const parts = setCookieHeader.split(/;\s*/);
  const sessionPair = parts.find((part) => part.startsWith(`${BACKEND_SESSION_COOKIE_NAME}=`));
  if (!sessionPair) {
    return null;
  }

  const value = sessionPair.split("=", 2)[1] ?? "";
  return value || null;
}
