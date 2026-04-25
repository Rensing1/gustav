import { beforeEach, describe, expect, it, vi } from "vitest";
import { isRedirect, redirect } from "@sveltejs/kit";

vi.mock("$lib/server/api", () => {
  class MockBackendRequestError extends Error {
    response: Response;

    constructor(response: Response) {
      super(`Backend request failed with ${response.status}`);
      this.response = response;
    }
  }

  return {
    BackendRequestError: MockBackendRequestError,
    requireBackendJson: vi.fn()
  };
});

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/learning/courses/course-1"),
  requireParentSpaceBootstrap: vi.fn()
}));

import { load } from "./+page.server";
import { requireBackendJson } from "$lib/server/api";
import { requireParentSpaceBootstrap } from "$lib/server/guards";

const requireBackendJsonMock = vi.mocked(requireBackendJson);
const requireParentSpaceBootstrapMock = vi.mocked(requireParentSpaceBootstrap);

function redirectError(status: Parameters<typeof redirect>[0], location: string) {
  try {
    redirect(status, location);
  } catch (caught) {
    return caught;
  }
  throw new Error("expected redirect");
}

describe("learning course route load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("preserves auth redirects from the shared space guard", async () => {
    requireParentSpaceBootstrapMock.mockRejectedValue(
      redirectError(302, "/?redirect=%2Flearning%2Fcourses%2Fcourse-1")
    );

    try {
      await load({
        fetch: vi.fn() as unknown as typeof fetch,
        cookies: {} as Parameters<typeof load>[0]["cookies"],
        params: { courseId: "course-1" },
        parent: vi.fn(async () => ({
          bootstrap: null,
          appSessionActive: false,
          theme: "light"
        })) as Parameters<typeof load>[0]["parent"],
        url: new URL("http://test.local/learning/courses/course-1")
      } as Parameters<typeof load>[0]);
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/?redirect=%2Flearning%2Fcourses%2Fcourse-1"
      });
    }

    expect(requireBackendJsonMock).not.toHaveBeenCalled();
  });
});
