import { describe, expect, it, vi } from "vitest";

const { backendRequestMock } = vi.hoisted(() => ({
  backendRequestMock: vi.fn()
}));

vi.mock("$lib/server/api", () => ({
  backendRequest: backendRequestMock
}));

import { proxyBackendWrite } from "./bff-proxy";

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
