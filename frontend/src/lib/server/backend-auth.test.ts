import { beforeEach, describe, expect, it, vi } from "vitest";

const { createTokenSessionMock, clearTokenSessionMock, readTokenSessionMock, jwtVerifyMock } = vi.hoisted(() => ({
  createTokenSessionMock: vi.fn(),
  clearTokenSessionMock: vi.fn(),
  readTokenSessionMock: vi.fn(),
  jwtVerifyMock: vi.fn()
}));

vi.mock("$env/dynamic/private", () => ({
  env: {
    ALLOWED_REGISTRATION_DOMAINS: "",
    FRONTEND_SESSION_SECRET: "test-secret",
    GUSTAV_ENV: "dev",
    KC_BASE_URL: "http://keycloak:8080",
    KC_CLIENT_ID: "gustav-web",
    KC_PUBLIC_BASE_URL: "https://id.localhost",
    KC_REALM: "gustav",
    ORIGIN: "https://app.localhost"
  }
}));

vi.mock("$lib/server/api", () => ({
  buildApiUrl: (path: string) => `http://backend.test${path}`
}));

vi.mock("$lib/server/session", () => ({
  clearTokenSession: clearTokenSessionMock,
  createTokenSession: createTokenSessionMock,
  readTokenSession: readTokenSessionMock
}));

vi.mock("jose", () => ({
  createRemoteJWKSet: vi.fn(() => ({})),
  jwtVerify: jwtVerifyMock
}));

import { handleAuthCallback, startLoginFlow, startRegisterFlow } from "./backend-auth";

class MemoryCookies {
  store = new Map<string, string>();
  setCalls: Array<[string, string, object]> = [];
  deleteCalls: Array<[string, object]> = [];

  get(name: string): string | undefined {
    return this.store.get(name);
  }

  set(name: string, value: string, options: object): void {
    this.store.set(name, value);
    this.setCalls.push([name, value, options]);
  }

  delete(name: string, options: object): void {
    this.store.delete(name);
    this.deleteCalls.push([name, options]);
  }
}

function decodeFlowCookie(rawCookie: string): { state: string; nonce: string; redirectPath: string | null } {
  const [payload] = rawCookie.split(".", 1);
  return JSON.parse(Buffer.from(payload, "base64url").toString("utf-8")) as {
    state: string;
    nonce: string;
    redirectPath: string | null;
  };
}

function createEvent(url: string, cookies: MemoryCookies, fetchMock: typeof fetch) {
  return {
    cookies,
    fetch: fetchMock,
    request: new Request(url),
    url: new URL(url)
  } as never;
}

function tokenResponse(): Response {
  return new Response(
    JSON.stringify({
      access_token: "access-token",
      refresh_token: "refresh-token",
      id_token: "id-token",
      expires_in: 300
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" }
    }
  );
}

describe("handleAuthCallback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fails closed when creating the server-side BFF session fails", async () => {
    const globalFetch = vi.fn<typeof fetch>().mockResolvedValue(tokenResponse());
    vi.stubGlobal("fetch", globalFetch);
    createTokenSessionMock.mockResolvedValue(null);
    clearTokenSessionMock.mockResolvedValue(undefined);
    readTokenSessionMock.mockResolvedValue(null);

    const cookies = new MemoryCookies();
    startLoginFlow(createEvent("https://app.localhost/auth/login?redirect=/profile", cookies, vi.fn() as never));
    const flow = decodeFlowCookie(String(cookies.get("gustav_bff_oidc_flow")));
    jwtVerifyMock.mockResolvedValue({ payload: { nonce: flow.nonce } });

    const eventFetch = vi.fn<typeof fetch>();
    const response = await handleAuthCallback(
      createEvent(`https://app.localhost/auth/callback?code=test-code&state=${flow.state}`, cookies, eventFetch)
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ error: "session_setup_failed" });
    expect(cookies.get("gustav_bff_oidc_flow")).toBeTruthy();
    expect(cookies.deleteCalls).toHaveLength(0);
    expect(eventFetch).not.toHaveBeenCalled();
  });

  it("rolls back the BFF session when app session sync fails", async () => {
    const globalFetch = vi.fn<typeof fetch>().mockResolvedValue(tokenResponse());
    vi.stubGlobal("fetch", globalFetch);
    createTokenSessionMock.mockResolvedValue({
      sessionId: "bff-session-1",
      accessToken: "access-token",
      refreshToken: "refresh-token",
      idToken: "id-token",
      expiresAt: 4102444800
    });
    clearTokenSessionMock.mockResolvedValue(undefined);
    readTokenSessionMock.mockResolvedValue(null);

    const cookies = new MemoryCookies();
    startLoginFlow(createEvent("https://app.localhost/auth/login?redirect=/profile", cookies, vi.fn() as never));
    const flow = decodeFlowCookie(String(cookies.get("gustav_bff_oidc_flow")));
    jwtVerifyMock.mockResolvedValue({ payload: { nonce: flow.nonce } });

    const eventFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthenticated" }), {
        status: 401,
        headers: { "content-type": "application/json" }
      })
    );

    const response = await handleAuthCallback(
      createEvent(`https://app.localhost/auth/callback?code=test-code&state=${flow.state}`, cookies, eventFetch)
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ error: "session_setup_failed" });
    expect(clearTokenSessionMock).toHaveBeenCalledWith(cookies, eventFetch);
    expect(cookies.get("gustav_bff_oidc_flow")).toBeTruthy();
    expect(cookies.deleteCalls).toHaveLength(0);
  });

  it("redirects the register callback back to the stored in-app target", async () => {
    const globalFetch = vi.fn<typeof fetch>().mockResolvedValue(tokenResponse());
    vi.stubGlobal("fetch", globalFetch);
    createTokenSessionMock.mockResolvedValue({
      sessionId: "bff-session-2",
      accessToken: "access-token",
      refreshToken: "refresh-token",
      idToken: "id-token",
      expiresAt: 4102444800
    });
    clearTokenSessionMock.mockResolvedValue(undefined);
    readTokenSessionMock.mockResolvedValue(null);

    const cookies = new MemoryCookies();
    const eventFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: { "set-cookie": "gustav_session=app-session; Path=/; HttpOnly" }
      })
    );

    startRegisterFlow(
      createEvent(
        "https://app.localhost/auth/register?login_hint=alice%40school.example&redirect=/teaching/courses/course-1",
        cookies,
        eventFetch
      )
    );
    const flow = decodeFlowCookie(String(cookies.get("gustav_bff_oidc_flow")));
    jwtVerifyMock.mockResolvedValue({ payload: { nonce: flow.nonce } });

    const response = await handleAuthCallback(
      createEvent(`https://app.localhost/auth/callback?code=test-code&state=${flow.state}`, cookies, eventFetch)
    );

    expect(flow.redirectPath).toBe("/teaching/courses/course-1");
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("/teaching/courses/course-1");
    expect(response.headers.get("set-cookie")).toContain("gustav_session=app-session");
    expect(cookies.get("gustav_bff_oidc_flow")).toBeUndefined();
    expect(cookies.deleteCalls).toHaveLength(1);
  });
});
