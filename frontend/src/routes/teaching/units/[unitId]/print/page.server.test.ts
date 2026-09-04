const { requireBackendJsonMock } = vi.hoisted(() => ({ requireBackendJsonMock: vi.fn() }));

vi.mock("$lib/server/api", () => ({
  requireBackendJson: requireBackendJsonMock
}));

import { beforeEach, describe, expect, it, vi } from "vitest";

import { load } from "./+page.server";

describe("printable-unit server loader", () => {
  beforeEach(() => {
    requireBackendJsonMock.mockReset();
    requireBackendJsonMock.mockResolvedValue({ unit: { id: "unit-1", title: "Netzwerke" } });
  });

  it("loads the author-scoped printable selection read model", async () => {
    const fetchFn = vi.fn();
    const cookies = {};
    const parent = vi.fn().mockResolvedValue({
      bootstrap: { spaces: ["teaching"], start_target: "/teaching" }
    });

    const result = await load({
      fetch: fetchFn,
      cookies,
      params: { unitId: "unit-1" },
      parent,
      url: new URL("https://app.localhost/teaching/units/unit-1/print")
    } as never);

    expect(requireBackendJsonMock).toHaveBeenCalledWith(
      fetchFn,
      cookies,
      "/api/teaching/units/unit-1/printable-content",
      { authRedirectPath: "/teaching/units/unit-1/print" }
    );
    expect(result).toMatchObject({ pageTitle: "Druckfassung erstellen" });
  });
});
