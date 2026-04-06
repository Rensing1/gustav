import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import type { RequestEvent } from "@sveltejs/kit";
import { createRemoteJWKSet, jwtVerify } from "jose";

import { env } from "$env/dynamic/private";
import { buildApiUrl } from "$lib/server/api";
import { clearTokenSession, createTokenSession, readTokenSession } from "$lib/server/session";

const DEFAULT_KC_BASE_URL = "http://keycloak:8080";
const DEFAULT_KC_PUBLIC_BASE_URL = "https://id.localhost";
const DEFAULT_KC_CLIENT_ID = "gustav-web";
const DEFAULT_KC_REALM = "gustav";
const FRONTEND_FLOW_COOKIE_NAME = "gustav_bff_oidc_flow";

type AuthFlowRecord = {
  state: string;
  codeVerifier: string;
  nonce: string;
  redirectPath: string | null;
  redirectUri: string;
  expiresAt: number;
};

type KeycloakTokenResponse = {
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

function frontendSessionSecret(): string {
  return env.FRONTEND_SESSION_SECRET || "CHANGE_ME_DEV";
}

function kcBaseUrl(): string {
  return env.KC_BASE_URL || DEFAULT_KC_BASE_URL;
}

function kcPublicBaseUrl(): string {
  return env.KC_PUBLIC_BASE_URL || DEFAULT_KC_PUBLIC_BASE_URL;
}

function kcRealm(): string {
  return env.KC_REALM || DEFAULT_KC_REALM;
}

function kcClientId(): string {
  return env.KC_CLIENT_ID || DEFAULT_KC_CLIENT_ID;
}

function noStoreHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  headers.set("cache-control", "private, no-store");
  return headers;
}

function createRedirectResponse(url: string): Response {
  return new Response(null, {
    status: 302,
    headers: noStoreHeaders({ location: url })
  });
}

function createJsonError(status: number, error: string): Response {
  return new Response(JSON.stringify({ error }), {
    status,
    headers: noStoreHeaders({ "content-type": "application/json" })
  });
}

async function syncAppSession(event: RequestEvent, accessToken: string): Promise<string | null> {
  try {
    const response = await event.fetch(buildApiUrl("/api/app/session-sync"), {
      method: "POST",
      headers: {
        authorization: `Bearer ${accessToken}`
      }
    });
    if (!response.ok) {
      return null;
    }
    return response.headers.get("set-cookie");
  } catch {
    return null;
  }
}

function randomBase64Url(bytes: number): string {
  return randomBytes(bytes).toString("base64url");
}

function createCodeChallenge(codeVerifier: string): string {
  return createHash("sha256").update(codeVerifier).digest("base64url");
}

function safeRedirectPath(path: string | null | undefined): string | null {
  if (!path || !path.startsWith("/")) {
    return null;
  }
  if (path.startsWith("//")) {
    return null;
  }
  return path;
}

function resolveAppBase(requestUrl: URL): string {
  const configuredOrigin = env.ORIGIN || requestUrl.origin;
  try {
    const configured = new URL(configuredOrigin);
    if (configured.host === requestUrl.host) {
      return requestUrl.origin;
    }
    return configured.origin;
  } catch {
    return requestUrl.origin;
  }
}

function resolveRedirectUri(requestUrl: URL): string {
  return `${resolveAppBase(requestUrl)}/auth/callback`;
}

function authEndpoint(): string {
  return `${kcPublicBaseUrl()}/realms/${kcRealm()}/protocol/openid-connect/auth`;
}

function tokenEndpoint(): string {
  return `${kcBaseUrl()}/realms/${kcRealm()}/protocol/openid-connect/token`;
}

function forgotEndpoint(): string {
  return `${kcPublicBaseUrl()}/realms/${kcRealm()}/login-actions/reset-credentials`;
}

function logoutEndpoint(): string {
  return `${kcPublicBaseUrl()}/realms/${kcRealm()}/protocol/openid-connect/logout`;
}

function issuer(): string {
  return `${kcPublicBaseUrl()}/realms/${kcRealm()}`;
}

function signFlowPayload(value: string): string {
  return createHmac("sha256", frontendSessionSecret()).update(value).digest("base64url");
}

function serializeFlowCookie(record: AuthFlowRecord): string {
  const payload = Buffer.from(JSON.stringify(record), "utf-8").toString("base64url");
  return `${payload}.${signFlowPayload(payload)}`;
}

function parseFlowCookie(value: string | undefined): AuthFlowRecord | null {
  if (!value) {
    return null;
  }
  const [payload, signature] = value.split(".", 2);
  if (!payload || !signature) {
    return null;
  }
  const expected = signFlowPayload(payload);
  try {
    if (!timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
      return null;
    }
  } catch {
    return null;
  }
  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf-8"));
    if (typeof parsed !== "object" || parsed === null) {
      return null;
    }
    return parsed as AuthFlowRecord;
  } catch {
    return null;
  }
}

function setFlowCookie(event: RequestEvent, record: AuthFlowRecord): void {
  event.cookies.set(FRONTEND_FLOW_COOKIE_NAME, serializeFlowCookie(record), {
    path: "/auth",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

function readFlowCookie(event: RequestEvent): AuthFlowRecord | null {
  const record = parseFlowCookie(event.cookies.get(FRONTEND_FLOW_COOKIE_NAME));
  if (!record) {
    return null;
  }
  if (record.expiresAt <= Math.floor(Date.now() / 1000)) {
    clearFlowCookie(event);
    return null;
  }
  return record;
}

function clearFlowCookie(event: RequestEvent): void {
  event.cookies.delete(FRONTEND_FLOW_COOKIE_NAME, {
    path: "/auth",
    httpOnly: true,
    sameSite: "lax",
    secure: useSecureCookie()
  });
}

function buildAuthorizationUrl(flow: AuthFlowRecord, extraParams?: Record<string, string>): string {
  const url = new URL(authEndpoint());
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", kcClientId());
  url.searchParams.set("redirect_uri", flow.redirectUri);
  url.searchParams.set("scope", "openid");
  url.searchParams.set("state", flow.state);
  url.searchParams.set("code_challenge", createCodeChallenge(flow.codeVerifier));
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("nonce", flow.nonce);
  if (extraParams) {
    for (const [key, value] of Object.entries(extraParams)) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

function createFlow(requestUrl: URL, redirectPath: string | null): AuthFlowRecord {
  return {
    state: randomBase64Url(24),
    codeVerifier: randomBase64Url(48),
    nonce: randomBase64Url(16),
    redirectPath,
    redirectUri: resolveRedirectUri(requestUrl),
    expiresAt: Math.floor(Date.now() / 1000) + 900
  };
}

function parseAllowedRegistrationDomains(raw: string | undefined): Set<string> {
  if (!raw) {
    return new Set();
  }
  return new Set(
    raw
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean)
  );
}

function isAllowedRegistrationEmail(email: string, allowedDomains: Set<string>): boolean {
  if (!allowedDomains.size) {
    return true;
  }
  const normalized = email.trim().toLowerCase();
  const separatorIndex = normalized.lastIndexOf("@");
  if (separatorIndex <= 0 || separatorIndex === normalized.length - 1) {
    return false;
  }
  const localPart = normalized.slice(0, separatorIndex);
  const domain = normalized.slice(separatorIndex + 1);
  return Boolean(localPart && domain && allowedDomains.has(`@${domain}`));
}

async function verifyIdToken(idToken: string, expectedNonce: string): Promise<void> {
  const jwks = createRemoteJWKSet(new URL(`${kcBaseUrl()}/realms/${kcRealm()}/protocol/openid-connect/certs`));
  const { payload } = await jwtVerify(idToken, jwks, {
    issuer: issuer(),
    audience: kcClientId()
  });
  if (String(payload.nonce || "") !== expectedNonce) {
    throw new Error("invalid_nonce");
  }
}

async function exchangeCodeForTokens(code: string, redirectUri: string, codeVerifier: string): Promise<KeycloakTokenResponse | null> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: kcClientId(),
    redirect_uri: redirectUri,
    code_verifier: codeVerifier
  });
  const response = await fetch(tokenEndpoint(), {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded"
    },
    body
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as KeycloakTokenResponse;
}

export function startLoginFlow(event: RequestEvent): Response {
  const flow = createFlow(event.url, safeRedirectPath(event.url.searchParams.get("redirect")));
  setFlowCookie(event, flow);
  return createRedirectResponse(buildAuthorizationUrl(flow));
}

export function startRegisterFlow(event: RequestEvent): Response {
  const loginHint = event.url.searchParams.get("login_hint")?.trim() || null;
  const allowedDomains = parseAllowedRegistrationDomains(env.ALLOWED_REGISTRATION_DOMAINS);
  if (loginHint && !isAllowedRegistrationEmail(loginHint, allowedDomains)) {
    return new Response(
      JSON.stringify({
        error: "invalid_email_domain",
        detail: "Die Registrierung ist nur mit einer Schul-E-Mail-Adresse erlaubt."
      }),
      {
        status: 400,
        headers: noStoreHeaders({ "content-type": "application/json" })
      }
    );
  }

  const flow = createFlow(event.url, null);
  setFlowCookie(event, flow);
  const extraParams: Record<string, string> = { kc_action: "register" };
  if (loginHint) {
    extraParams.login_hint = loginHint;
  }
  return createRedirectResponse(buildAuthorizationUrl(flow, extraParams));
}

export function startForgotFlow(event: RequestEvent): Response {
  const url = new URL(forgotEndpoint());
  const loginHint = event.url.searchParams.get("login_hint");
  if (loginHint) {
    url.searchParams.set("login_hint", loginHint);
  }
  return createRedirectResponse(url.toString());
}

export function startPasswordFlow(event: RequestEvent): Response {
  const redirectPath = safeRedirectPath(event.url.searchParams.get("redirect")) || "/profile";
  const flow = createFlow(event.url, redirectPath);
  setFlowCookie(event, flow);
  return createRedirectResponse(buildAuthorizationUrl(flow, { kc_action: "UPDATE_PASSWORD" }));
}

export async function handleAuthCallback(event: RequestEvent): Promise<Response> {
  const code = event.url.searchParams.get("code");
  const state = event.url.searchParams.get("state");
  if (!code || !state) {
    clearFlowCookie(event);
    return createJsonError(400, "invalid_code_or_state");
  }

  const flow = readFlowCookie(event);
  if (!flow || flow.state !== state) {
    clearFlowCookie(event);
    return createJsonError(400, "invalid_code_or_state");
  }

  const tokens = await exchangeCodeForTokens(code, flow.redirectUri, flow.codeVerifier);
  if (!tokens?.id_token || !tokens.access_token) {
    clearFlowCookie(event);
    return createJsonError(400, "token_exchange_failed");
  }

  try {
    await verifyIdToken(tokens.id_token, flow.nonce);
  } catch (error) {
    clearFlowCookie(event);
    const message = error instanceof Error && error.message === "invalid_nonce" ? "invalid_nonce" : "invalid_id_token";
    return createJsonError(400, message);
  }

  createTokenSession(event.cookies, {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token ?? null,
    idToken: tokens.id_token,
    expiresAt: Math.floor(Date.now() / 1000) + Math.max(60, Number(tokens.expires_in || 300))
  });
  clearFlowCookie(event);
  const appSessionCookie = await syncAppSession(event, tokens.access_token);
  const response = createRedirectResponse(flow.redirectPath || "/");
  if (appSessionCookie) {
    response.headers.append("set-cookie", appSessionCookie);
  }
  return response;
}

export function handleLogout(event: RequestEvent): Response {
  const tokenSession = readTokenSession(event.cookies);
  const redirectPath = safeRedirectPath(event.url.searchParams.get("redirect")) || "/auth/logout/success";
  clearTokenSession(event.cookies);

  const url = new URL(logoutEndpoint());
  url.searchParams.set("post_logout_redirect_uri", `${resolveAppBase(event.url)}${redirectPath}`);
  if (tokenSession?.idToken) {
    url.searchParams.set("id_token_hint", tokenSession.idToken);
  } else {
    url.searchParams.set("client_id", kcClientId());
  }

  return createRedirectResponse(url.toString());
}
