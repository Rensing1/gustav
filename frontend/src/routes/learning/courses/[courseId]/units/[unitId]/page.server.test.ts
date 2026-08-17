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
    backendRequest: vi.fn(),
    requireBackendJson: vi.fn()
  };
});

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/learning/courses/course-1/units/unit-1"),
  requireParentSpaceBootstrap: vi.fn(async () => ({
    user: { sub: "student-1", name: "Test", roles: ["student"] }
  })),
  requireSpaceBootstrap: vi.fn(async () => ({
    user: { sub: "student-1", name: "Test", roles: ["student"] }
  }))
}));

import { actions, load } from "./+page.server";
import { backendRequest, requireBackendJson } from "$lib/server/api";
import { requireSpaceBootstrap } from "$lib/server/guards";

const requireBackendJsonMock = vi.mocked(requireBackendJson);
const backendRequestMock = vi.mocked(backendRequest);
const requireSpaceBootstrapMock = vi.mocked(requireSpaceBootstrap);
const finalizationIdempotencyKey = "finalize-123e4567-e89b-42d3-a456-426614174000";

function setFinalSubmissionIntent(form: FormData): void {
  form.set("submission_intent", "submit");
  form.set("finalization_idempotency_key", finalizationIdempotencyKey);
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

function requestWithFormData(form: FormData): Parameters<typeof actions.default>[0]["request"] {
  return {
    formData: async () => form
  } as Parameters<typeof actions.default>[0]["request"];
}

function redirectError(status: Parameters<typeof redirect>[0], location: string) {
  try {
    redirect(status, location);
  } catch (caught) {
    return caught;
  }
  throw new Error("expected redirect");
}

function mockModularLoad() {
  requireBackendJsonMock.mockImplementation(async (_fetch, _cookies, path) => {
    if (path === "/api/learning/courses/course-1/units") {
      return [
        {
          unit: {
            id: "unit-1",
            title: "Europa",
            unit_type: "modular"
          },
          position: 1
        }
      ];
    }
    if (path === "/api/learning/views/learner-home") {
      return {
        current_courses: [{ id: "course-1", title: "10RL Politik-Wirtschaft" }],
        past_courses: []
      };
    }
    if (path === "/api/learning/courses/course-1/units/unit-1/modules/graph") {
      return {
        unit: { id: "unit-1", title: "Europa", unit_type: "modular" },
        phases: [],
        modules: [],
        edges: []
      };
    }
    if (path === "/api/learning/courses/course-1/units/unit-1/modules/module-7?include=materials,tasks") {
      return {
        module: {
          id: "module-7",
          title: "Bedeutung Europas",
          unit_id: "unit-1",
          phase_id: "phase-1",
          position_in_phase: 1
        },
        materials: [],
        tasks: [
          {
            id: "task-1",
            instruction_md: "Erkläre den Zusammenhang.",
            criteria: [],
            kind: "native"
          }
        ]
      };
    }
    if (path === "/api/learning/courses/course-1/tasks/task-1/submissions?limit=10&offset=0") {
      return [{ id: "submission-1", intent: "submit", attempt_nr: 1 }];
    }
    throw new Error(`unexpected_path:${path}`);
  });
}

describe("learning unit route actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses module_id from the form when resolving modular feedback submissions", async () => {
    mockModularLoad();
    backendRequestMock.mockResolvedValue(jsonResponse({ id: "submission-1", analysis_status: "pending" }));

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    form.set("text_body", "Mein Entwurf");
    form.set("submission_intent", "feedback");

    const result = await actions.default({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      request: requestWithFormData(form),
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
    } as Parameters<typeof actions.default>[0]);

    expect(requireBackendJsonMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/units/unit-1/modules/module-7?include=materials,tasks",
      expect.objectContaining({
        authRedirectPath: "/learning/courses/course-1/units/unit-1"
      })
    );
    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/tasks/task-1/submissions",
      expect.objectContaining({
        method: "POST",
        includeSameOrigin: true
      })
    );
    expect(result).toEqual({
      feedbackRequestedTaskId: "task-1",
      feedbackSubmissionId: "submission-1",
      historyTaskId: "task-1",
      message: "feedback_pending",
      pendingIntent: "feedback",
      submissionMode: "text"
    });
  });

  it("keeps final submissions inline and marks them as submit-pending", async () => {
    mockModularLoad();
    backendRequestMock.mockResolvedValue(
      jsonResponse(
        {
          id: "submission-2",
          intent: "submit",
          analysis_status: "completed",
          created_at: "2026-04-07T12:00:00+00:00",
          files: [{ mime: "application/pdf", size: 2048, url: "http://storage.local/submission.pdf" }]
        },
        201
      )
    );

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    setFinalSubmissionIntent(form);

    const result = await actions.default({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      request: requestWithFormData(form),
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
    } as Parameters<typeof actions.default>[0]);

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/tasks/task-1/submissions/finalize",
      expect.objectContaining({
        method: "POST",
        includeSameOrigin: true,
        headers: {
          "content-type": "application/json",
          "idempotency-key": finalizationIdempotencyKey
        }
      })
    );
    expect(result).toEqual({
      finalizedTaskId: "task-1",
      finalizedSubmission: {
        id: "submission-2",
        intent: "submit",
        analysis_status: "completed",
        created_at: "2026-04-07T12:00:00+00:00",
        files: [{ mime: "application/pdf", size: 2048, url: "http://storage.local/submission.pdf" }]
      },
      message: "submitted"
    });
  });

  it("rejects a final submission without the reviewed submission key", async () => {
    mockModularLoad();

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    form.set("submission_intent", "submit");

    const result = await actions.default({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      request: requestWithFormData(form),
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
    } as Parameters<typeof actions.default>[0]);

    expect(backendRequestMock).not.toHaveBeenCalled();
    expect(result).toMatchObject({
      status: 400,
      data: {
        message: "Die endgültige Abgabe ist nicht mehr aktuell. Bitte lade die Aufgabe neu.",
        taskId: "task-1"
      }
    });
  });

  it.each([
    [409, "draft_not_ready", "Die Rückmeldung wird noch verarbeitet. Bitte versuche die endgültige Abgabe gleich noch einmal."],
    [409, "draft_missing", "Es gibt noch keinen rückgemeldeten Entwurf. Hole zuerst eine Rückmeldung ein."],
    [400, "max_attempts_exceeded", "Für diese Aufgabe sind keine weiteren endgültigen Abgaben möglich."],
    [
      503,
      "submission_persistence_unavailable",
      "Die endgültige Abgabe konnte wegen einer vorübergehenden Störung nicht gespeichert werden. Bitte versuche es erneut."
    ]
  ])("translates final submission error %s/%s", async (status, detail, expectedMessage) => {
    mockModularLoad();
    backendRequestMock.mockResolvedValue(jsonResponse({ error: "error", detail }, status));

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    setFinalSubmissionIntent(form);

    const result = await actions.default({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      request: requestWithFormData(form),
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
    } as Parameters<typeof actions.default>[0]);

    expect(result).toMatchObject({
      status,
      data: { message: expectedMessage, taskId: "task-1" }
    });
  });

  it("rejects upload submissions in the route action so browser-direct upload stays the primary path", async () => {
    mockModularLoad();

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    form.set("submission_intent", "feedback");
    form.set("upload_file", new File(["pdf"], "loesung.pdf", { type: "application/pdf" }));

    const result = await actions.default({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      request: requestWithFormData(form),
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
    } as Parameters<typeof actions.default>[0]);

    expect(requireBackendJsonMock).not.toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/tasks/task-1/upload-intents",
      expect.anything()
    );
    expect(result).toMatchObject({
      status: 400,
      data: {
        message: "Datei-Uploads benötigen aktiviertes JavaScript.",
        taskId: "task-1"
      }
    });
  });

  it("rethrows auth redirects from the shared learning-space guard", async () => {
    requireSpaceBootstrapMock.mockRejectedValueOnce(
      redirectError(302, "/?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1")
    );

    const form = new FormData();
    form.set("task_id", "task-1");

    try {
      await actions.default({
        fetch: vi.fn() as unknown as typeof fetch,
        cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
        params: { courseId: "course-1", unitId: "unit-1" },
        request: requestWithFormData(form),
        url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
      } as Parameters<typeof actions.default>[0]);
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1"
      });
    }
  });

  it("passes the current page path to final submissions so shared auth recovery can avoid generic failures", async () => {
    mockModularLoad();
    backendRequestMock.mockRejectedValueOnce(
      redirectError(302, "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1")
    );

    const form = new FormData();
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("unit_type", "modular");
    form.set("module_id", "module-7");
    setFinalSubmissionIntent(form);

    try {
      await actions.default({
        fetch: vi.fn() as unknown as typeof fetch,
        cookies: {} as Parameters<typeof actions.default>[0]["cookies"],
        params: { courseId: "course-1", unitId: "unit-1" },
        request: requestWithFormData(form),
        url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
      } as Parameters<typeof actions.default>[0]);
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1"
      });
    }

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/tasks/task-1/submissions/finalize",
      expect.objectContaining({
        authRedirectPath: "/learning/courses/course-1/units/unit-1",
        method: "POST"
      })
    );
  });
});

describe("learning unit route load", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps overview view when the URL explicitly requests it even if a module param exists", async () => {
    mockModularLoad();

    const result = (await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: false,
        theme: "light",
        workspaceLayout: "standard"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1?view=overview&module=module-7")
    } as Parameters<typeof load>[0])) as Exclude<Awaited<ReturnType<typeof load>>, void>;

    expect(requireBackendJsonMock).not.toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/units/unit-1/modules/module-7?include=materials,tasks"
    );
    expect(result.initialView).toBe("overview");
    expect(result.activeModule).toBeNull();
  });

  it("treats legacy module-only links as content view for backward compatibility", async () => {
    mockModularLoad();

    const result = (await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: false,
        theme: "light",
        workspaceLayout: "standard"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1?module=module-7")
    } as Parameters<typeof load>[0])) as Exclude<Awaited<ReturnType<typeof load>>, void>;

    expect(requireBackendJsonMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/units/unit-1/modules/module-7?include=materials,tasks",
      expect.objectContaining({
        authRedirectPath: "/learning/courses/course-1/units/unit-1"
      })
    );
    expect(result.initialView).toBe("content");
    expect(result.activeModule?.module.id).toBe("module-7");
  });

  it("loads canonical task and result parameters without requiring legacy history links", async () => {
    mockModularLoad();

    const result = (await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      parent: vi.fn(async () => ({ bootstrap: null, appSessionActive: false, theme: "light", workspaceLayout: "standard" })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1?module=module-7&task=task-1&panel=result")
    } as Parameters<typeof load>[0])) as Exclude<Awaited<ReturnType<typeof load>>, void>;

    expect(result.requestedTaskId).toBe("task-1");
    expect(result.initialPanel).toBe("result");
    expect(result.historyTaskId).toBe("task-1");
    expect(result.history).toHaveLength(1);
  });

  it("passes the current page path to protected read-model calls for silent auth continuation", async () => {
    mockModularLoad();

    await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof load>[0]["cookies"],
      params: { courseId: "course-1", unitId: "unit-1" },
      parent: vi.fn(async () => ({
        bootstrap: null,
        appSessionActive: false,
        theme: "light",
        workspaceLayout: "standard"
      })) as Parameters<typeof load>[0]["parent"],
      url: new URL("http://test.local/learning/courses/course-1/units/unit-1?module=module-7")
    } as Parameters<typeof load>[0]);

    expect(requireBackendJsonMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/units",
      expect.objectContaining({
        authRedirectPath: "/learning/courses/course-1/units/unit-1"
      })
    );
  });

  it("rethrows continuation redirects from later loader requests instead of showing the generic learning error", async () => {
    requireBackendJsonMock.mockRejectedValueOnce(
      redirectError(302, "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1")
    );

    try {
      await load({
        fetch: vi.fn() as unknown as typeof fetch,
        cookies: {} as Parameters<typeof load>[0]["cookies"],
        params: { courseId: "course-1", unitId: "unit-1" },
        parent: vi.fn(async () => ({
          bootstrap: {
            user: { sub: "student-1", name: "Test", role: "student", roles: ["student"] },
            start_target: "/learning",
            spaces: ["learning"]
          },
          appSessionActive: true,
          theme: "light",
          workspaceLayout: "standard"
        })) as Parameters<typeof load>[0]["parent"],
        url: new URL("http://test.local/learning/courses/course-1/units/unit-1")
      } as Parameters<typeof load>[0]);
      throw new Error("expected redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      expect(caught).toMatchObject({
        status: 302,
        location: "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1"
      });
    }
  });
});
