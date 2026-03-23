import { randomUUID } from "node:crypto";

import type { Cookies } from "@sveltejs/kit";

import { env } from "$env/dynamic/private";

export const FRONTEND_SESSION_COOKIE_NAME = "gustav_bff_session";
const DEFAULT_KC_BASE_URL = "http://keycloak:8080";
const DEFAULT_KC_CLIENT_ID = "gustav-web";
const DEFAULT_KC_REALM = "gustav";
const TOKEN_REFRESH_LEEWAY_SECONDS = 30;

export type FrontendTokenSession = {
  sessionId: string;
  accessToken: string;
  refreshToken: string | null;
  idToken: string;
  expiresAt: number;
};

const TOKEN_SESSIONS = new Map<string, FrontendTokenSession>();

type KeycloakRefreshResponse = {
  access_token?: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
};

function useSecureCookie(): boolean {
  if ((env.ORIGIN || "").startsWith("https://")) {
    return true;
  }
  return (env.NODE_ENV || "").toLowerCase() === "production";
}

function kcBaseUrl(): string {
  return env.KC_BASE_URL || DEFAULT_KC_BASE_URL;
}

function kcClientId(): string {
  return env.KC_CLIENT_ID || DEFAULT_KC_CLIENT_ID;
}

function kcRealm(): string {
  return env.KC_REALM || DEFAULT_KC_REALM;
}

function tokenEndpoint(): string {
  return `${kcBaseUrl()}/realms/${kcRealm()}/protocol/openid-connect/token`;
}

function nowEpochSeconds(): number {
  return Math.floor(Date.now() / 1000);
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
  return record.expiresAt <= nowEpochSeconds();
}

function expiresSoon(record: FrontendTokenSession): boolean {
  return record.expiresAt <= nowEpochSeconds() + TOKEN_REFRESH_LEEWAY_SECONDS;
}

function readStoredTokenSession(cookies: Cookies): FrontendTokenSession | null {
  const sessionId = readFrontendSessionCookie(cookies);
  if (!sessionId) {
    return null;
  }
  return TOKEN_SESSIONS.get(sessionId) ?? null;
}

function replaceTokenSession(
  cookies: Cookies,
  current: FrontendTokenSession,
  tokens: KeycloakRefreshResponse
): FrontendTokenSession {
  const nextRecord: FrontendTokenSession = {
    sessionId: current.sessionId,
    accessToken: tokens.access_token || current.accessToken,
    refreshToken: tokens.refresh_token ?? current.refreshToken,
    idToken: tokens.id_token ?? current.idToken,
    expiresAt: nowEpochSeconds() + Math.max(60, Number(tokens.expires_in || 300))
  };
  TOKEN_SESSIONS.set(current.sessionId, nextRecord);
  setFrontendSessionCookie(cookies, current.sessionId);
  return nextRecord;
}

async function refreshTokenSession(
  cookies: Cookies,
  current: FrontendTokenSession,
  fetchFn: typeof fetch
): Promise<FrontendTokenSession | null> {
  if (!current.refreshToken) {
    if (isExpired(current)) {
      clearTokenSession(cookies);
      return null;
    }
    return current;
  }

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: kcClientId(),
    refresh_token: current.refreshToken
  });
  const response = await fetchFn(tokenEndpoint(), {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded"
    },
    body
  });

  if (!response.ok) {
    if (isExpired(current)) {
      clearTokenSession(cookies);
      return null;
    }
    return current;
  }

  const tokens = (await response.json()) as KeycloakRefreshResponse;
  if (!tokens.access_token) {
    if (isExpired(current)) {
      clearTokenSession(cookies);
      return null;
    }
    return current;
  }

  return replaceTokenSession(cookies, current, tokens);
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
  const record = readStoredTokenSession(cookies);
  if (!record) {
    return null;
  }
  if (isExpired(record)) {
    clearTokenSession(cookies);
    return null;
  }
  return record;
}

export async function readFreshTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch,
  options?: { forceRefresh?: boolean }
): Promise<FrontendTokenSession | null> {
  const record = readStoredTokenSession(cookies);
  if (!record) {
    return null;
  }
  if (!options?.forceRefresh && !expiresSoon(record)) {
    return record;
  }
  return await refreshTokenSession(cookies, record, fetchFn);
}

export function clearTokenSession(cookies: Cookies): void {
  const sessionId = readFrontendSessionCookie(cookies);
  if (sessionId) {
    TOKEN_SESSIONS.delete(sessionId);
  }
  clearFrontendSessionCookie(cookies);
}
