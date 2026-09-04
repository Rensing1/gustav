const { backendRequestMock } = vi.hoisted(() => ({ backendRequestMock: vi.fn() }));

vi.mock("$lib/server/api", () => ({ backendRequest: backendRequestMock }));

import { beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./+server";

describe("printable-unit download proxy", () => {
  beforeEach(() => backendRequestMock.mockReset());

  it("forwards selected IDs with same-origin protection and preserves safe download headers", async () => {
    backendRequestMock.mockResolvedValue(
      new Response(btoa("%PDF-result"), {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'attachment; filename="gustav-netzwerke-druckfassung.pdf"'
        }
      })
    );
    const form = new FormData();
    form.append("material_id", "material-1");
    form.append("task_id", "task-1");
    const request = new Request("https://app.localhost/teaching/units/unit-1/print/download", {
      method: "POST",
      body: form
    });

    const response = await POST({
      fetch: vi.fn(),
      cookies: {},
      params: { unitId: "unit-1" },
      request
    } as never);

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      {},
      "/api/teaching/units/unit-1/printable-pdf",
      {
        method: "POST",
        body: JSON.stringify({ material_ids: ["material-1"], task_ids: ["task-1"] }),
        headers: { "content-type": "application/json" },
        includeSameOrigin: true
      }
    );
    expect(response.headers.get("content-disposition")).toBe(
      'attachment; filename="gustav-netzwerke-druckfassung.pdf"'
    );
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
});
