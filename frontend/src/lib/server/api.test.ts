import { describe, expect, it, vi } from "vitest";
import { isRedirect } from "@sveltejs/kit";

const { readFreshTokenSessionMock } = vi.hoisted(() => ({
  readFreshTokenSessionMock: vi.fn()
}));

vi.mock("$env/dynamic/private", () => ({
  env: {
    API_INTERNAL_BASE_URL: "http://backend.test"
  }
}));

vi.mock("$lib/server/session", () => ({
  buildBackendAuthorizationHeader: (accessToken: string | null | undefined) => accessToken ? `Bearer ${accessToken}` : null,
  readFreshTokenSession: readFreshTokenSessionMock,
  readFrontendSessionCookie: (cookies: { get(name: string): string | undefined }) => cookies.get("gustav_bff_session") ?? null
}));

import { backendRequest, readAppSessionActive } from "./api";

class MemoryCookies {
  constructor(private readonly values: Map<string, string>) {}

  get(name: string): string | undefined {
    return this.values.get(name);
  }
}

describe("readAppSessionActive", () => {
  it("validates the existing app session by forwarding only the app session cookie", async () => {
    const cookies = new MemoryCookies(new Map([["gustav_session", "app-session-1"]]));
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ sub: "user-1" })));

    const active = await readAppSessionActive(fetchMock, cookies as never);

    expect(active).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("http://backend.test/api/me", {
      method: "GET",
      headers: {
        cookie: "gustav_session=app-session-1"
      }
    });
  });

  it("does not attempt continuity without an app session cookie", async () => {
    const fetchMock = vi.fn<typeof fetch>();

    const active = await readAppSessionActive(fetchMock, new MemoryCookies(new Map()) as never);

    expect(active).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("backendRequest auth continuity", () => {
  it("refreshes once on 401 and returns the retried backend response", async () => {
    readFreshTokenSessionMock
      .mockResolvedValueOnce({ accessToken: "expired-token" })
      .mockResolvedValueOnce({ accessToken: "fresh-token" });
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const response = await backendRequest(fetchMock, new MemoryCookies(new Map()) as never, "/api/protected", {
      authRedirectPath: "/learning"
    });
    const retriedHeaders = fetchMock.mock.calls[1]?.[1]?.headers as Headers;

    expect(response.status).toBe(200);
    expect(readFreshTokenSessionMock).toHaveBeenNthCalledWith(2, expect.anything(), fetchMock, { forceRefresh: true });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://backend.test/api/protected");
    expect(retriedHeaders.get("authorization")).toBe("Bearer fresh-token");
  });

  it("redirects final recoverable 401 responses to silent continuation", async () => {
    readFreshTokenSessionMock.mockResolvedValue(null);
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 })
    );

    try {
      await backendRequest(
        fetchMock,
        new MemoryCookies(new Map([["gustav_bff_session", "bff-session-1"]])) as never,
        "/api/protected",
        { authRedirectPath: "/learning/courses/course-1?module=module-7" }
      );
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%3Fmodule%3Dmodule-7"
      });
    }
  });

  it("uses the app session as a recoverable signal when the BFF bearer is unavailable", async () => {
    readFreshTokenSessionMock.mockResolvedValue(null);
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ sub: "student-1" }), { status: 200 }));

    try {
      await backendRequest(
        fetchMock,
        new MemoryCookies(new Map([["gustav_session", "app-session-1"]])) as never,
        "/api/app/session-bootstrap",
        { authRedirectPath: "/learning" }
      );
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning"
      });
      expect(infoSpy).toHaveBeenCalledWith("auth.continuity", {
        reason: "app_session_active_without_bearer",
        redirect: "/learning"
      });
      infoSpy.mockRestore();
    }
  });

  it("redirects final unrecoverable 401 responses to the visible login entry", async () => {
    readFreshTokenSessionMock.mockResolvedValue(null);
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 })
    );

    try {
      await backendRequest(fetchMock, new MemoryCookies(new Map()) as never, "/api/protected", {
        authRedirectPath: "/learning"
      });
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/?redirect=%2Flearning"
      });
    }
  });

  it("keeps final 401 responses as responses when no browser redirect path is provided", async () => {
    readFreshTokenSessionMock.mockResolvedValue(null);
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 })
    );

    const response = await backendRequest(fetchMock, new MemoryCookies(new Map()) as never, "/api/internal");

    expect(response.status).toBe(401);
  });
});
