import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/bff-proxy", () => ({
  proxyBackendRead: vi.fn()
}));

import { GET } from "./+server";
import { proxyBackendRead } from "$lib/server/bff-proxy";

const proxyBackendReadMock = vi.mocked(proxyBackendRead);

describe("teacher home live-unit BFF endpoint", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the selected course units through the authenticated BFF session", async () => {
    proxyBackendReadMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          course: { id: "course-1", title: "Politik 10L", href: "/live?course_id=course-1" },
          units: [{ id: "unit-1", title: "Europäische Union", position: 1, href: "/live?course_id=course-1&unit_id=unit-1" }]
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
            "cache-control": "private, no-store"
          }
        }
      )
    );

    const response = await GET({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof GET>[0]["cookies"],
      params: { courseId: "course-1" }
    } as Parameters<typeof GET>[0]);

    expect(proxyBackendReadMock).toHaveBeenCalledWith({
      fetchFn: expect.any(Function),
      cookies: expect.anything(),
      path: "/api/live/views/courses/course-1/units"
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
});
