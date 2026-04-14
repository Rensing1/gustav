import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/bff-proxy", () => ({
  proxyBackendRead: vi.fn()
}));

import { GET } from "./+server";
import { proxyBackendRead } from "$lib/server/bff-proxy";

const proxyBackendReadMock = vi.mocked(proxyBackendRead);

describe("live summary BFF endpoint", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards the request to the teaching live summary endpoint", async () => {
    proxyBackendReadMock.mockResolvedValue(
      new Response(JSON.stringify({
        cursor: "2026-04-13T10:00:00+00:00",
        tasks: [],
        rows: []
      }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const response = await GET({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof GET>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      url: new URL("http://test.local/live/courses/course-1/units/unit-1/summary")
    } as Parameters<typeof GET>[0]);

    expect(proxyBackendReadMock).toHaveBeenCalledWith({
      fetchFn: expect.any(Function),
      cookies: expect.anything(),
      path: "/api/teaching/courses/course-1/units/unit-1/submissions/summary"
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
    await expect(response.json()).resolves.toEqual({
      cursor: "2026-04-13T10:00:00+00:00",
      tasks: [],
      rows: []
    });
  });
});
