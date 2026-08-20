import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/api", () => ({
  backendRequest: vi.fn(),
  requireBackendJson: vi.fn()
}));

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/profile"),
  requireParentSessionBootstrap: vi.fn()
}));

vi.mock("$lib/server/session", () => ({
  readFreshTokenSession: vi.fn()
}));

import { load } from "./+page.server";
import { requireBackendJson } from "$lib/server/api";

const requireBackendJsonMock = vi.mocked(requireBackendJson);

describe("profile route load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not request CLI token metadata for a student", async () => {
    requireBackendJsonMock.mockResolvedValueOnce({
      user: { sub: "student-1", name: "Lena", role: "student", roles: ["student"] },
      display_name: "Lena",
      email: "student@example.com",
      first_name: "Lena",
      last_name: "Lernend",
      name_locked_until: null,
      name_can_edit: true,
      password_change_href: "/auth/password"
    });

    const result = await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: true,
        theme: "light",
        workspaceLayout: "compact"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/profile")
    } as Parameters<typeof load>[0]);

    expect(requireBackendJsonMock).toHaveBeenCalledTimes(1);
    expect(requireBackendJsonMock).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      "/api/app/profile",
      expect.anything()
    );
    expect(result).toMatchObject({ cliTokens: [] });
  });
});
