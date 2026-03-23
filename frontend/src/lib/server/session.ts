import { randomUUID } from "node:crypto";

import type { Cookies } from "@sveltejs/kit";

import { env } from "$env/dynamic/private";

export const FRONTEND_SESSION_COOKIE_NAME = "gustav_bff_session";

export type FrontendTokenSession = {
  sessionId: string;
  accessToken: string;
  refreshToken: string | null;
  idToken: string;
  expiresAt: number;
};

const TOKEN_SESSIONS = new Map<string, FrontendTokenSession>();

function useSecureCookie(): boolean {
  if ((env.ORIGIN || "").startsWith("https://")) {
    return true;
  }
  return (env.NODE_ENV || "").toLowerCase() === "production";
}

export function buildBackendAuthorizationHeader(accessToken: string | null | undefined): string | null {
  if (!accessToken) {
    return null;
  }
  return `Bearer ${accessToken}`;
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

function isExpired(record: FrontendTokenSession): boolean {
  return record.expiresAt <= Math.floor(Date.now() / 1000);
}

export function createTokenSession(
  cookies: Cookies,
  tokens: {
    accessToken: string;
    refreshToken?: string | null;
    idToken: string;
    expiresAt: number;
  }
): FrontendTokenSession {
  const sessionId = randomUUID();
  const record: FrontendTokenSession = {
    sessionId,
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken ?? null,
    idToken: tokens.idToken,
    expiresAt: tokens.expiresAt
  };
  TOKEN_SESSIONS.set(sessionId, record);
  setFrontendSessionCookie(cookies, sessionId);
  return record;
}

export function readTokenSession(cookies: Cookies): FrontendTokenSession | null {
  const sessionId = readFrontendSessionCookie(cookies);
  if (!sessionId) {
    return null;
  }
  const record = TOKEN_SESSIONS.get(sessionId) ?? null;
  if (!record) {
    return null;
  }
  if (isExpired(record)) {
    TOKEN_SESSIONS.delete(sessionId);
    clearFrontendSessionCookie(cookies);
    return null;
  }
  return record;
}

export function clearTokenSession(cookies: Cookies): void {
  const sessionId = readFrontendSessionCookie(cookies);
  if (sessionId) {
    TOKEN_SESSIONS.delete(sessionId);
  }
  clearFrontendSessionCookie(cookies);
}
