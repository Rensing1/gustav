import { beforeEach, describe, expect, it, vi } from "vitest";
import { isRedirect } from "@sveltejs/kit";

vi.mock("$lib/server/api", () => ({
  requireBackendJson: vi.fn()
}));

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/live"),
  requireParentSpaceBootstrap: vi.fn()
}));

import { load } from "./+page.server";
import { requireBackendJson } from "$lib/server/api";
import { requireParentSpaceBootstrap } from "$lib/server/guards";

const requireBackendJsonMock = vi.mocked(requireBackendJson);
const requireParentSpaceBootstrapMock = vi.mocked(requireParentSpaceBootstrap);

function summaryPayload() {
  return {
    cursor: "2026-04-13T10:00:00+00:00",
    tasks: [
      { id: "task-1", instruction_md: "### Aufgabe 1", position: 1, kind: "native" },
      { id: "task-2", instruction_md: "### Aufgabe 2", position: 2, kind: "native" }
    ],
    rows: [
      {
        student: { sub: "student-1", name: "Anna" },
        tasks: [
          { task_id: "task-1", has_submission: true, average_score: 8, created_at: "2026-04-13T10:00:00+00:00" },
          { task_id: "task-2", has_submission: false, average_score: null, created_at: null }
        ]
      }
    ]
  };
}

describe("live page load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireParentSpaceBootstrapMock.mockResolvedValue({
      user: { sub: "teacher-1", name: "Ada", role: "teacher", roles: ["teacher"] },
      start_target: "/teaching",
      spaces: ["teaching"]
    });
  });

  it("redirects stale task selections to the canonical live URL before loading detail data", async () => {
    requireBackendJsonMock.mockImplementation(async (_fetch, _cookies, path) => {
      if (path === "/api/teaching/courses?limit=25&offset=0") {
        return [{ id: "course-1", title: "Mathe 9b" }];
      }
      if (path === "/api/live/views/courses/course-1/units") {
        return {
          course: { id: "course-1", title: "Mathe 9b" },
          units: [{ id: "unit-1", title: "Brueche", position: 1 }]
        };
      }
      if (path === "/api/teaching/courses/course-1/units/unit-1/submissions/summary") {
        return summaryPayload();
      }
      throw new Error(`unexpected_path:${path}`);
    });

    await expect(load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: false,
        theme: "light"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-stale")
    } as Parameters<typeof load>[0])).rejects.toSatisfy((caught: unknown) => {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1"
      });
      return true;
    });
  });

  it("drops invalid student selections from the live URL before loading detail data", async () => {
    requireBackendJsonMock.mockImplementation(async (_fetch, _cookies, path) => {
      if (path === "/api/teaching/courses?limit=25&offset=0") {
        return [{ id: "course-1", title: "Mathe 9b" }];
      }
      if (path === "/api/live/views/courses/course-1/units") {
        return {
          course: { id: "course-1", title: "Mathe 9b" },
          units: [{ id: "unit-1", title: "Brueche", position: 1 }]
        };
      }
      if (path === "/api/teaching/courses/course-1/units/unit-1/submissions/summary") {
        return summaryPayload();
      }
      throw new Error(`unexpected_path:${path}`);
    });

    await expect(load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: false,
        theme: "light"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/live?course_id=course-1&unit_id=unit-1&student_sub=student-stale&task_id=task-2")
    } as Parameters<typeof load>[0])).rejects.toSatisfy((caught: unknown) => {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/live?course_id=course-1&unit_id=unit-1"
      });
      return true;
    });
  });
});
