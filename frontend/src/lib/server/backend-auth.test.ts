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

import { handleAuthCallback, handleLogout, startLoginFlow, startRegisterFlow } from "./backend-auth";

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

describe("handleLogout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prefers the BFF id_token hint over a backend client_id-only redirect", async () => {
    readTokenSessionMock.mockResolvedValue({
      sessionId: "bff-session-logout",
      accessToken: "access-token",
      refreshToken: "refresh-token",
      idToken: "bff-id-token",
      expiresAt: 4102444800
    });
    clearTokenSessionMock.mockResolvedValue(undefined);

    const cookies = new MemoryCookies();
    const eventFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(null, {
          status: 302,
          headers: {
            location:
              "https://id.localhost/realms/gustav/protocol/openid-connect/logout?client_id=gustav-web&post_logout_redirect_uri=https%3A%2F%2Fapp.localhost%2Fauth%2Flogout%2Fsuccess",
            "set-cookie": "gustav_session=; Path=/; Max-Age=0; HttpOnly"
          }
        })
      );

    const response = await handleLogout(
      createEvent("https://app.localhost/auth/logout?redirect=/auth/logout/success", cookies, eventFetch)
    );

    expect(clearTokenSessionMock).toHaveBeenCalledWith(cookies, eventFetch);
    expect(eventFetch).toHaveBeenCalledOnce();
    const [requestUrl, requestInit] = eventFetch.mock.calls[0] || [];
    expect(String(requestUrl)).toBe("http://backend.test/auth/logout?redirect=%2Fauth%2Flogout%2Fsuccess");
    expect(requestInit).toMatchObject({
      method: "GET",
      redirect: "manual",
      headers: expect.objectContaining({
        "x-gustav-id-token-hint": "bff-id-token"
      })
    });
    expect(response.status).toBe(302);
    const location = response.headers.get("location") || "";
    expect(location).toBe(
      "https://id.localhost/realms/gustav/protocol/openid-connect/logout?client_id=gustav-web&post_logout_redirect_uri=https%3A%2F%2Fapp.localhost%2Fauth%2Flogout%2Fsuccess"
    );
    expect(response.headers.get("set-cookie")).toContain("gustav_session=");
  });

  it("falls back to client_id when no BFF id_token is available", async () => {
    readTokenSessionMock.mockResolvedValue(null);
    clearTokenSessionMock.mockResolvedValue(undefined);

    const cookies = new MemoryCookies();
    const eventFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          location: "http://backend.test/auth/logout?redirect=%2Fcourses"
        }
      })
    );

    const response = await handleLogout(createEvent("https://app.localhost/auth/logout?redirect=/courses", cookies, eventFetch));

    expect(response.status).toBe(302);
    const [requestUrl, requestInit] = eventFetch.mock.calls[0] || [];
    expect(String(requestUrl)).toBe("http://backend.test/auth/logout?redirect=%2Fcourses");
    expect(requestInit).toMatchObject({
      headers: expect.not.objectContaining({
        "x-gustav-id-token-hint": expect.anything()
      })
    });
    const location = response.headers.get("location") || "";
    expect(location).toBe("http://backend.test/auth/logout?redirect=%2Fcourses");
  });

  it("keeps the logout success redirect stable when only the backend app session is still present", async () => {
    readTokenSessionMock.mockResolvedValue(null);
    clearTokenSessionMock.mockResolvedValue(undefined);

    const cookies = new MemoryCookies();
    const eventFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          location:
            "https://id.localhost/realms/gustav/protocol/openid-connect/logout?client_id=gustav-web&post_logout_redirect_uri=https%3A%2F%2Fapp.localhost%2Fauth%2Flogout%2Fsuccess",
          "set-cookie": "gustav_session=; Path=/; Max-Age=0; HttpOnly"
        }
      })
    );

    const response = await handleLogout(
      createEvent("https://app.localhost/auth/logout?redirect=/auth/logout/success", cookies, eventFetch)
    );

    expect(response.status).toBe(302);
    const location = response.headers.get("location") || "";
    expect(location).toContain("client_id=gustav-web");
    expect(location).toContain("post_logout_redirect_uri=https%3A%2F%2Fapp.localhost%2Fauth%2Flogout%2Fsuccess");
    expect(response.headers.get("set-cookie")).toContain("gustav_session=");
  });
});
