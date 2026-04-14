import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/bff-proxy", () => ({
  proxyBackendRead: vi.fn()
}));

import { GET } from "./+server";
import { proxyBackendRead } from "$lib/server/bff-proxy";

const proxyBackendReadMock = vi.mocked(proxyBackendRead);

describe("live detail-sheet BFF endpoint", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards the student and task selection to the backend detail-sheet endpoint", async () => {
    proxyBackendReadMock.mockResolvedValue(
      new Response(JSON.stringify({
        submission: { id: "submission-1" }
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
      url: new URL("http://test.local/live/courses/course-1/units/unit-1/detail-sheet?student_sub=student-1&task_id=task-2")
    } as Parameters<typeof GET>[0]);

    expect(proxyBackendReadMock).toHaveBeenCalledWith({
      fetchFn: expect.any(Function),
      cookies: expect.anything(),
      path: "/api/live/views/courses/course-1/units/unit-1/detail-sheet?student_sub=student-1&task_id=task-2"
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("vary")).toBe("Origin");
    await expect(response.json()).resolves.toEqual({
      submission: { id: "submission-1" }
    });
  });
});
