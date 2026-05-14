import type { Cookies } from "@sveltejs/kit";

import { env } from "$env/dynamic/private";

const DEFAULT_API_INTERNAL_BASE_URL = "http://gustav-alpha2:8000";
const DEFAULT_FRONTEND_SESSION_COOKIE_NAME = "gustav_bff_session";
const DEFAULT_KC_BASE_URL = "http://keycloak:8080";
const DEFAULT_KC_CLIENT_ID = "gustav-web";
const DEFAULT_KC_REALM = "gustav";
const TOKEN_REFRESH_LEEWAY_SECONDS = 30;
const BFF_SESSION_PATH = "/backend-internal/app/bff-session";

export type FrontendTokenSession = {
  sessionId: string;
  accessToken: string;
  refreshToken: string | null;
  idToken: string;
  expiresAt: number;
  sessionExpiresAt: number;
};

type KeycloakRefreshResponse = {
  access_token?: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
};

type StoredFrontendTokenSession = {
  session_id: string;
  access_token: string;
  refresh_token?: string | null;
  id_token: string;
  expires_at: number;
  session_expires_at?: number;
};

function useSecureCookie(): boolean {
  if ((env.ORIGIN || "").startsWith("https://")) {
    return true;
  }
  return (env.NODE_ENV || "").toLowerCase() === "production";
}

function frontendSessionCookieName(): string {
  return env.FRONTEND_SESSION_COOKIE_NAME || DEFAULT_FRONTEND_SESSION_COOKIE_NAME;
}

function internalBffSecret(): string {
  return String(env.BFF_INTERNAL_SHARED_SECRET || "").trim();
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

function buildApiUrl(path: string): string {
  const baseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  return new URL(path, baseUrl).toString();
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
  return cookies.get(frontendSessionCookieName()) ?? null;
}

export function setFrontendSessionCookie(cookies: Cookies, sessionId: string): void {
  cookies.set(frontendSessionCookieName(), sessionId, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

export function clearFrontendSessionCookie(cookies: Cookies): void {
  cookies.delete(frontendSessionCookieName(), {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

function isExpired(record: FrontendTokenSession): boolean {
  return record.expiresAt <= nowEpochSeconds();
}

function isSessionExpired(record: FrontendTokenSession): boolean {
  return record.sessionExpiresAt <= nowEpochSeconds();
}

function expiresSoon(record: FrontendTokenSession): boolean {
  return record.expiresAt <= nowEpochSeconds() + TOKEN_REFRESH_LEEWAY_SECONDS;
}

function toFrontendTokenSession(record: StoredFrontendTokenSession): FrontendTokenSession {
  return {
    sessionId: record.session_id,
    accessToken: record.access_token,
    refreshToken: record.refresh_token ?? null,
    idToken: record.id_token,
    expiresAt: record.expires_at,
    sessionExpiresAt: record.session_expires_at ?? record.expires_at
  };
}

async function fetchStoredTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch,
  options?: { clearMissing?: boolean }
): Promise<FrontendTokenSession | null> {
  const sessionId = readFrontendSessionCookie(cookies);
  if (!sessionId) {
    return null;
  }
  const response = await fetchFn(buildApiUrl(BFF_SESSION_PATH), {
    method: "GET",
    headers: {
      "x-gustav-bff-session": sessionId,
      "x-gustav-internal-secret": internalBffSecret()
    }
  });
  if (response.status === 204 || response.status === 401) {
    if (options?.clearMissing === false) {
      return null;
    }
    clearFrontendSessionCookie(cookies);
    return null;
  }
  if (!response.ok) {
    return null;
  }
  return toFrontendTokenSession((await response.json()) as StoredFrontendTokenSession);
}

async function readConcurrentFreshSession(
  cookies: Cookies,
  fetchFn: typeof fetch
): Promise<FrontendTokenSession | null> {
  const latest = await fetchStoredTokenSession(cookies, fetchFn, { clearMissing: false });
  if (!latest || isSessionExpired(latest) || isExpired(latest)) {
    return null;
  }
  return latest;
}

async function clearExpiredSessionUnlessRecovered(
  cookies: Cookies,
  fetchFn: typeof fetch
): Promise<FrontendTokenSession | null> {
  const recovered = await readConcurrentFreshSession(cookies, fetchFn);
  if (recovered) {
    return recovered;
  }
  await clearTokenSession(cookies, fetchFn);
  return null;
}

function logTokenRefreshFailure(status: number, recovered: string): void {
  console.info("auth.session", {
    reason: "token_refresh_failed",
    status,
    recovered
  });
}

async function persistTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch,
  tokens: {
    accessToken: string;
    refreshToken?: string | null;
    idToken: string;
    expiresAt: number;
  },
  sessionId?: string | null
): Promise<FrontendTokenSession | null> {
  const headers: Record<string, string> = {
    "content-type": "application/json"
  };
  if (sessionId) {
    headers["x-gustav-bff-session"] = sessionId;
  }
  headers["x-gustav-internal-secret"] = internalBffSecret();
  const requestInit = {
    headers,
    body: JSON.stringify({
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken ?? null,
      id_token: tokens.idToken,
      expires_at: tokens.expiresAt
    })
  };
  const response = sessionId
    ? await fetchFn(buildApiUrl(BFF_SESSION_PATH), { method: "PATCH", ...requestInit })
    : await fetchFn(buildApiUrl(BFF_SESSION_PATH), { method: "PUT", ...requestInit });
  if (!response.ok) {
    return null;
  }
  const record = toFrontendTokenSession((await response.json()) as StoredFrontendTokenSession);
  setFrontendSessionCookie(cookies, record.sessionId);
  return record;
}

async function refreshTokenSession(
  cookies: Cookies,
  current: FrontendTokenSession,
  fetchFn: typeof fetch
): Promise<FrontendTokenSession | null> {
  if (!current.refreshToken) {
    if (isExpired(current)) {
      return await clearExpiredSessionUnlessRecovered(cookies, fetchFn);
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
      const recovered = await clearExpiredSessionUnlessRecovered(cookies, fetchFn);
      logTokenRefreshFailure(response.status, recovered ? "concurrent_session" : "cleared_expired_session");
      return recovered;
    }
    logTokenRefreshFailure(response.status, "kept_unexpired_session");
    return current;
  }

  const tokens = (await response.json()) as KeycloakRefreshResponse;
  if (!tokens.access_token) {
    if (isExpired(current)) {
      return await clearExpiredSessionUnlessRecovered(cookies, fetchFn);
    }
    return current;
  }

  const persisted = await persistTokenSession(
    cookies,
    fetchFn,
    {
      accessToken: tokens.access_token || current.accessToken,
      refreshToken: tokens.refresh_token ?? current.refreshToken,
      idToken: tokens.id_token ?? current.idToken,
      expiresAt: nowEpochSeconds() + Math.max(60, Number(tokens.expires_in || 300))
    },
    current.sessionId
  );
  if (persisted) {
    return persisted;
  }
  if (isExpired(current)) {
    return await clearExpiredSessionUnlessRecovered(cookies, fetchFn);
  }
  return current;
}

export async function createTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch,
  tokens: {
    accessToken: string;
    refreshToken?: string | null;
    idToken: string;
    expiresAt: number;
  }
): Promise<FrontendTokenSession | null> {
  return await persistTokenSession(cookies, fetchFn, tokens, null);
}

export async function readTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch
): Promise<FrontendTokenSession | null> {
  const record = await fetchStoredTokenSession(cookies, fetchFn);
  if (!record) {
    return null;
  }
  if (isSessionExpired(record)) {
    await clearTokenSession(cookies, fetchFn);
    return null;
  }
  return record;
}

export async function readFreshTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch,
  options?: { forceRefresh?: boolean }
): Promise<FrontendTokenSession | null> {
  const record = await fetchStoredTokenSession(cookies, fetchFn);
  if (!record) {
    return null;
  }
  if (isSessionExpired(record)) {
    await clearTokenSession(cookies, fetchFn);
    return null;
  }
  if (!options?.forceRefresh && !expiresSoon(record)) {
    return record;
  }
  return await refreshTokenSession(cookies, record, fetchFn);
}

export async function clearTokenSession(
  cookies: Cookies,
  fetchFn: typeof fetch
): Promise<void> {
  const sessionId = readFrontendSessionCookie(cookies);
  clearFrontendSessionCookie(cookies);
  if (!sessionId) {
    return;
  }
  await fetchFn(buildApiUrl(BFF_SESSION_PATH), {
    method: "DELETE",
    headers: {
      "x-gustav-bff-session": sessionId,
      "x-gustav-internal-secret": internalBffSecret()
    }
  });
}
