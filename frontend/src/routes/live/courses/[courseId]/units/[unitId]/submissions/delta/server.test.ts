import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/bff-proxy", () => ({
  proxyBackendRead: vi.fn()
}));

import { GET } from "./+server";
import { proxyBackendRead } from "$lib/server/bff-proxy";

const proxyBackendReadMock = vi.mocked(proxyBackendRead);

describe("live delta BFF endpoint", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("preserves 204 responses from the backend delta endpoint", async () => {
    proxyBackendReadMock.mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: {
          "cache-control": "private, no-store",
          vary: "Origin"
        }
      })
    );

    const response = await GET({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof GET>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      url: new URL("http://test.local/live/courses/course-1/units/unit-1/submissions/delta?updated_since=2026-04-13T10:00:00.000Z")
    } as Parameters<typeof GET>[0]);

    expect(proxyBackendReadMock).toHaveBeenCalledWith({
      fetchFn: expect.any(Function),
      cookies: expect.anything(),
      path: "/api/teaching/courses/course-1/units/unit-1/submissions/delta?updated_since=2026-04-13T10%3A00%3A00.000Z"
    });
    expect(response.status).toBe(204);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
  });

  it("returns the backend JSON payload unchanged on 200", async () => {
    proxyBackendReadMock.mockResolvedValue(
      new Response(JSON.stringify({ cells: [{ changed_at: "2026-04-13T10:01:00.000Z" }] }), {
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
      url: new URL("http://test.local/live/courses/course-1/units/unit-1/submissions/delta?updated_since=2026-04-13T10:00:00.000Z")
    } as Parameters<typeof GET>[0]);

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
    await expect(response.json()).resolves.toEqual({
      cells: [{ changed_at: "2026-04-13T10:01:00.000Z" }]
    });
  });
});
