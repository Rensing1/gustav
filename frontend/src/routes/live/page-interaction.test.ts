import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import type { LiveSummaryPayload } from "$lib/types/home";

import {
  buildDashboardViewModel,
  createLiveWorkspaceController,
  navigateWithLiveSelectionFallback
} from "./page-state";

function submission(taskId: string, textBody: string) {
  return {
    id: `submission-${taskId}`,
    task_id: taskId,
    student_sub: "student-1",
    instruction_md: "### Aufgabe",
    created_at: "2026-04-13T10:00:00+00:00",
    completed_at: "2026-04-13T10:01:00+00:00",
    kind: "text",
    text_body: textBody,
    feedback_md: `Feedback zu ${taskId}`,
    files: []
  };
}

function summary(studentName = "Anna"): LiveSummaryPayload {
  return {
    cursor: "2026-04-13T10:00:00+00:00",
    tasks: [
      {
        id: "task-1",
        instruction_md: "### Aufgabe",
        position: 1,
        kind: "native"
      },
      {
        id: "task-2",
        instruction_md: "### Aufgabe",
        position: 2,
        kind: "native"
      }
    ],
    rows: [
      {
        student: {
          sub: "student-1",
          name: studentName
        },
        tasks: [
          {
            task_id: "task-1",
            has_submission: true,
            average_score: 4.0,
            created_at: "2026-04-13T10:00:00+00:00"
          },
          {
            task_id: "task-2",
            has_submission: true,
            average_score: 8.0,
            created_at: "2026-04-13T09:00:00+00:00"
          }
        ]
      },
      {
        student: {
          sub: "student-2",
          name: "Ben"
        },
        tasks: [
          {
            task_id: "task-1",
            has_submission: false,
            average_score: null,
            created_at: null
          },
          {
            task_id: "task-2",
            has_submission: true,
            average_score: 9.0,
            created_at: "2026-04-13T11:00:00+00:00"
          }
        ]
      }
    ]
  };
}

describe("live workspace controller", () => {
  it("routes browser fetch 401 responses through shared auth recovery before live errors", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");

    expect(routeSource).toContain('import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";');
    expect(routeSource.match(/handleBrowserAuthRecovery\(/g)?.length).toBe(4);
    expect(routeSource).toContain('throw new Error("auth_recovery_started")');
    expect(routeSource).not.toContain("live_summary_fetch_failed_401");
    expect(routeSource).not.toContain("live_detail_fetch_failed_401");
    expect(routeSource).not.toContain("live_delta_fetch_failed_401");
  });

  it("loads and renders the safe transcript for a dialog submission", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const routeSource = readFileSync(path.resolve(currentDir, "+page.svelte"), "utf8");
    const serverSource = readFileSync(path.resolve(currentDir, "+page.server.ts"), "utf8");

    expect(routeSource).toContain("/submissions/${encodeURIComponent(submission.id)}/dialog");
    expect(routeSource).toContain("Mit Satzanfang-Hilfe");
    expect(routeSource).toContain("Abschlussantwort");
    expect(serverSource).toContain("/submissions/${encodeURIComponent(detail.submission.id)}/dialog");
  });

  it("derives row and task links locally from the current live selection", () => {
    const dashboard = buildDashboardViewModel({
      summary: summary(),
      selection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      detail: submission("task-1", "Antwort von Anna"),
      course: {
        id: "course-1",
        title: "Mathe 9b",
        href: "/live?course_id=course-1"
      },
      unit: {
        id: "unit-1",
        title: "Brueche",
        position: 1,
        href: "/live?course_id=course-1&unit_id=unit-1"
      },
      user: {
        sub: "teacher-1",
        name: "Ada",
        role: "teacher",
        roles: ["teacher"]
      }
    });

    expect(dashboard?.rows[0]?.href).toBe("/live?course_id=course-1&unit_id=unit-1&student_sub=student-1");
    expect(dashboard?.selected_student_panel?.tasks[0]?.href).toBe(
      "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1"
    );
  });

  it("switches the student locally and only loads the selected detail", async () => {
    const syncHref = vi.fn();
    const fetchSummary = vi.fn();
    const fetchDetail = vi.fn().mockResolvedValue(submission("task-1", "Antwort von Anna"));
    const fetchDelta = vi.fn();

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: null,
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: null,
        taskId: null
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref,
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await controller.selectStudent("student-1");

    expect(fetchSummary).not.toHaveBeenCalled();
    expect(fetchDetail).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1",
      studentSub: "student-1",
      taskId: "task-1"
    });
    expect(controller.getState().studentSub).toBe("student-1");
    expect(controller.getState().taskId).toBe("task-1");
    expect(controller.getState().detail?.text_body).toBe("Antwort von Anna");
    expect(syncHref).toHaveBeenCalledWith("/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1");
  });

  it("keeps the active sort when the teacher switches tasks and only loads detail data", async () => {
    const fetchSummary = vi.fn();
    const fetchDetail = vi.fn().mockResolvedValue(submission("task-2", "Antwort zu task-2"));

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Antwort zu task-1"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta: vi.fn()
    });

    controller.toggleSort("average");
    await controller.selectTask("task-2");

    expect(fetchSummary).not.toHaveBeenCalled();
    expect(fetchDetail).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1",
      studentSub: "student-1",
      taskId: "task-2"
    });
    expect(controller.getState().activeSortKey).toBe("average");
    expect(controller.getState().activeSortDirection).toBe("desc");
    expect(controller.getState().taskId).toBe("task-2");
    expect(controller.getState().detail?.text_body).toBe("Antwort zu task-2");
  });

  it("reloads the summary on delta changes and refreshes the active detail only when the open cell changed", async () => {
    const fetchSummary = vi.fn().mockResolvedValue({
      ...summary("Anna Adler"),
      cursor: "2026-04-13T10:02:00+00:00"
    });
    const fetchDetail = vi.fn().mockResolvedValue(submission("task-1", "Neue Antwort aus dem Polling"));
    const fetchDelta = vi.fn()
      .mockResolvedValueOnce({ status: 204 })
      .mockResolvedValueOnce({
        status: 200,
        cursor: "2026-04-13T10:02:00+00:00",
        cells: [{ student_sub: "student-1", task_id: "task-1", changed_at: "2026-04-13T10:02:00+00:00" }]
      });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await controller.poll();
    expect(fetchSummary).not.toHaveBeenCalled();
    expect(fetchDetail).not.toHaveBeenCalled();
    expect(controller.getState().cursor).toBe("2026-04-13T10:00:00+00:00");

    await controller.poll();
    expect(fetchSummary).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1"
    });
    expect(fetchDetail).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1",
      studentSub: "student-1",
      taskId: "task-1"
    });
    expect(controller.getState().cursor).toBe("2026-04-13T10:02:00+00:00");
    expect(controller.getState().detail?.text_body).toBe("Neue Antwort aus dem Polling");
  });

  it("keeps the newer delta cursor when the refreshed summary still exposes an older snapshot cursor", async () => {
    const fetchSummary = vi.fn().mockResolvedValue({
      ...summary("Anna Adler"),
      cursor: "2026-04-13T10:01:00+00:00"
    });
    const fetchDetail = vi.fn().mockResolvedValue(submission("task-1", "Neue Antwort aus dem Polling"));
    const fetchDelta = vi.fn().mockResolvedValue({
      status: 200,
      cursor: "2026-04-13T10:02:00+00:00",
      cells: [{ student_sub: "student-1", task_id: "task-1", changed_at: "2026-04-13T10:02:00+00:00" }]
    });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await controller.poll();

    expect(fetchSummary).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1"
    });
    expect(controller.getState().cursor).toBe("2026-04-13T10:02:00+00:00");
  });

  it("keeps the previous cursor when the summary refresh fails after a delta hit", async () => {
    const fetchSummary = vi.fn().mockRejectedValue(new Error("summary offline"));
    const fetchDetail = vi.fn();
    const fetchDelta = vi.fn().mockResolvedValue({
      status: 200,
      cursor: "2026-04-13T10:02:00+00:00",
      cells: [{ student_sub: "student-1", task_id: "task-1", changed_at: "2026-04-13T10:02:00+00:00" }]
    });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await expect(controller.poll()).rejects.toThrow("summary offline");
    expect(controller.getState().cursor).toBe("2026-04-13T10:00:00+00:00");
    expect(controller.getState().detail?.text_body).toBe("Vorherige Antwort");
    expect(fetchDetail).not.toHaveBeenCalled();
  });

  it("keeps the previous cursor when the active detail refresh fails after summary reload", async () => {
    const fetchSummary = vi.fn().mockResolvedValue(summary("Anna Adler"));
    const fetchDetail = vi.fn().mockRejectedValue(new Error("detail offline"));
    const fetchDelta = vi.fn().mockResolvedValue({
      status: 200,
      cursor: "2026-04-13T10:02:00+00:00",
      cells: [{ student_sub: "student-1", task_id: "task-1", changed_at: "2026-04-13T10:02:00+00:00" }]
    });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await expect(controller.poll()).rejects.toThrow("detail offline");
    expect(controller.getState().cursor).toBe("2026-04-13T10:00:00+00:00");
    expect(controller.getState().detail?.text_body).toBe("Vorherige Antwort");
  });

  it("reloads detail when the refreshed summary re-canonicalizes the selected task", async () => {
    const nextSummary = {
      ...summary("Anna Adler"),
      rows: [
        {
          student: {
            sub: "student-1",
            name: "Anna Adler"
          },
          tasks: [
            {
              task_id: "task-2",
              has_submission: true,
              average_score: 8.0,
              created_at: "2026-04-13T10:03:00+00:00"
            }
          ]
        },
        summary().rows[1]
      ]
    };
    const fetchSummary = vi.fn().mockResolvedValue(nextSummary);
    const fetchDetail = vi.fn().mockResolvedValue(submission("task-2", "Neue kanonische Antwort"));
    const fetchDelta = vi.fn().mockResolvedValue({
      status: 200,
      cursor: "2026-04-13T10:02:00+00:00",
      cells: [{ student_sub: "student-2", task_id: "task-2", changed_at: "2026-04-13T10:02:00+00:00" }]
    });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await controller.poll();

    expect(fetchDetail).toHaveBeenCalledWith({
      courseId: "course-1",
      unitId: "unit-1",
      studentSub: "student-1",
      taskId: "task-2"
    });
    expect(controller.getState().taskId).toBe("task-2");
    expect(controller.getState().detail?.text_body).toBe("Neue kanonische Antwort");
    expect(controller.getState().cursor).toBe("2026-04-13T10:02:00+00:00");
  });

  it("keeps the previous state when re-canonicalized detail reload fails after summary refresh", async () => {
    const nextSummary = {
      ...summary("Anna Adler"),
      rows: [
        {
          student: {
            sub: "student-1",
            name: "Anna Adler"
          },
          tasks: [
            {
              task_id: "task-2",
              has_submission: true,
              average_score: 8.0,
              created_at: "2026-04-13T10:03:00+00:00"
            }
          ]
        },
        summary().rows[1]
      ]
    };
    const fetchSummary = vi.fn().mockResolvedValue(nextSummary);
    const fetchDetail = vi.fn().mockRejectedValue(new Error("detail offline"));
    const fetchDelta = vi.fn().mockResolvedValue({
      status: 200,
      cursor: "2026-04-13T10:02:00+00:00",
      cells: [{ student_sub: "student-2", task_id: "task-2", changed_at: "2026-04-13T10:02:00+00:00" }]
    });

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Vorherige Antwort"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary,
      fetchDetail,
      fetchDelta
    });

    await expect(controller.poll()).rejects.toThrow("detail offline");
    expect(controller.getState().taskId).toBe("task-1");
    expect(controller.getState().cursor).toBe("2026-04-13T10:00:00+00:00");
    expect(controller.getState().detail?.text_body).toBe("Vorherige Antwort");
  });

  it("ignores stale detail responses when a newer task selection wins", async () => {
    type SubmissionPayload = ReturnType<typeof submission>;
    let resolveFirst: (value: SubmissionPayload) => void = () => undefined;
    let resolveSecond: (value: SubmissionPayload) => void = () => undefined;

    const controller = createLiveWorkspaceController({
      initialSummary: summary(),
      initialDetail: submission("task-1", "Startzustand"),
      initialSelection: {
        courseId: "course-1",
        unitId: "unit-1",
        studentSub: "student-1",
        taskId: "task-1"
      },
      initialCursor: "2026-04-13T10:00:00+00:00",
      syncHref: vi.fn(),
      fetchSummary: vi.fn(),
      fetchDetail: vi.fn()
        .mockImplementationOnce(
          () =>
            new Promise<SubmissionPayload>((resolve) => {
              resolveFirst = resolve;
            })
        )
        .mockImplementationOnce(
          () =>
            new Promise<SubmissionPayload>((resolve) => {
              resolveSecond = resolve;
            })
        ),
      fetchDelta: vi.fn()
    });

    const first = controller.selectTask("task-1");
    const second = controller.selectTask("task-2");

    resolveFirst(submission("task-1", "Veraltete Antwort"));
    await first;
    expect(controller.getState().taskId).toBe("task-1");
    expect(controller.getState().detail?.text_body).toBe("Startzustand");

    resolveSecond(submission("task-2", "Aktuelle Antwort"));
    await second;
    expect(controller.getState().taskId).toBe("task-2");
    expect(controller.getState().detail?.text_body).toBe("Aktuelle Antwort");
  });

  it("falls back to canonical navigation when local student selection fails", async () => {
    const goto = vi.fn().mockResolvedValue(undefined);
    const trySelect = vi.fn().mockRejectedValue(new Error("detail offline"));

    const mode = await navigateWithLiveSelectionFallback({
      href: "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1",
      trySelect,
      goto
    });

    expect(mode).toBe("fallback");
    expect(goto).toHaveBeenCalledWith(
      "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1",
      {
        keepFocus: true,
        noScroll: true,
        replaceState: true
      }
    );
  });

  it("keeps browser auth recovery navigation instead of falling back to live navigation", async () => {
    const goto = vi.fn().mockResolvedValue(undefined);
    const trySelect = vi.fn().mockRejectedValue(new Error("auth_recovery_started"));

    const mode = await navigateWithLiveSelectionFallback({
      href: "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-1",
      trySelect,
      goto
    });

    expect(mode).toBe("auth-recovery");
    expect(goto).not.toHaveBeenCalled();
  });

  it("falls back to canonical navigation when local task selection fails", async () => {
    const goto = vi.fn().mockResolvedValue(undefined);
    const trySelect = vi.fn().mockRejectedValue(new Error("detail offline"));

    const mode = await navigateWithLiveSelectionFallback({
      href: "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-2",
      trySelect,
      goto
    });

    expect(mode).toBe("fallback");
    expect(goto).toHaveBeenCalledWith(
      "/live?course_id=course-1&unit_id=unit-1&student_sub=student-1&task_id=task-2",
      {
        keepFocus: true,
        noScroll: true,
        replaceState: true
      }
    );
  });
});
