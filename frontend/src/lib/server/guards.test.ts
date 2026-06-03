import { beforeEach, describe, expect, it, vi } from "vitest";
import { isRedirect } from "@sveltejs/kit";

const { readAppSessionActiveMock, readTypedJsonOrNullMock } = vi.hoisted(() => ({
  readAppSessionActiveMock: vi.fn(),
  readTypedJsonOrNullMock: vi.fn()
}));

vi.mock("$lib/server/api", () => ({
  readAppSessionActive: readAppSessionActiveMock,
  readTypedJsonOrNull: readTypedJsonOrNullMock
}));

import {
  requireParentSessionBootstrap,
  requireSessionBootstrap
} from "./guards";

describe("session bootstrap guards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("continues silently when a parent layout reports an active app session", async () => {
    try {
      await requireParentSessionBootstrap(
        async () => ({ bootstrap: null, appSessionActive: true }),
        "/learning/courses/course-1?module=module-7"
      );
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%3Fmodule%3Dmodule-7"
      });
    }
  });

  it("continues silently before showing login when no parent app session is active", async () => {
    try {
      await requireParentSessionBootstrap(
        async () => ({ bootstrap: null, appSessionActive: false }),
        "/teaching"
      );
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Fteaching"
      });
    }
  });

  it("continues silently from direct guards when the stable app session is active", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const cookies = {} as Parameters<typeof requireSessionBootstrap>[1];
    readTypedJsonOrNullMock.mockResolvedValueOnce(null);
    readAppSessionActiveMock.mockResolvedValueOnce(true);

    try {
      await requireSessionBootstrap(fetchMock, cookies, "/learning/courses/course-1/units/unit-1");
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1"
      });
    }

    expect(readAppSessionActiveMock).not.toHaveBeenCalled();
  });

  it("continues silently from direct guards before showing login when no app session is active", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const cookies = {} as Parameters<typeof requireSessionBootstrap>[1];
    readTypedJsonOrNullMock.mockResolvedValueOnce(null);
    readAppSessionActiveMock.mockResolvedValueOnce(false);

    try {
      await requireSessionBootstrap(fetchMock, cookies, "/profile");
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Fprofile"
      });
    }
  });
});
