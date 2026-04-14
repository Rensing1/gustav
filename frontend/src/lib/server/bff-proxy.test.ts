import { describe, expect, it, vi } from "vitest";

const { backendRequestMock } = vi.hoisted(() => ({
  backendRequestMock: vi.fn()
}));

vi.mock("$lib/server/api", () => ({
  backendRequest: backendRequestMock
}));

import { proxyBackendWrite } from "./bff-proxy";
import { proxyBackendRead } from "./bff-proxy";

describe("proxyBackendWrite", () => {
  it("preserves security headers from backend write responses", async () => {
    backendRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const response = await proxyBackendWrite({
      fetchFn: vi.fn() as never,
      cookies: {} as never,
      path: "/api/teaching/units/unit-1/sections/reorder",
      method: "POST",
      body: { position: 1 }
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
    await expect(response.json()).resolves.toEqual({ ok: true });
  });
});

describe("proxyBackendRead", () => {
  it("forwards read requests with same-origin enforcement enabled", async () => {
    backendRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ rows: [] }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const fetchFn = vi.fn() as never;
    const cookies = {} as never;

    await proxyBackendRead({
      fetchFn,
      cookies,
      path: "/api/teaching/courses/course-1/units/unit-1/submissions/summary"
    });

    expect(backendRequestMock).toHaveBeenCalledWith(
      fetchFn,
      cookies,
      "/api/teaching/courses/course-1/units/unit-1/submissions/summary",
      {
        method: "GET",
        includeSameOrigin: true
      }
    );
  });

  it("preserves security headers from backend read responses", async () => {
    backendRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ rows: [] }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const response = await proxyBackendRead({
      fetchFn: vi.fn() as never,
      cookies: {} as never,
      path: "/api/teaching/courses/course-1/units/unit-1/submissions/summary"
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
    await expect(response.json()).resolves.toEqual({ rows: [] });
  });

  it("preserves 204 responses and security headers on read endpoints", async () => {
    backendRequestMock.mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: {
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const response = await proxyBackendRead({
      fetchFn: vi.fn() as never,
      cookies: {} as never,
      path: "/api/teaching/courses/course-1/units/unit-1/submissions/delta?updated_since=2026-04-13T10:00:00.000Z"
    });

    expect(response.status).toBe(204);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
  });
});
