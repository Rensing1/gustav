import { describe, expect, it, vi, beforeEach } from "vitest";

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
  requireSpaceBootstrap: vi.fn(async () => ({
    user: { sub: "student-1", name: "Test", roles: ["student"] }
  }))
}));

import { actions } from "./+page.server";
import { backendRequest, requireBackendJson } from "$lib/server/api";

const requireBackendJsonMock = vi.mocked(requireBackendJson);
const backendRequestMock = vi.mocked(backendRequest);

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
        courses: [{ id: "course-1", title: "10RL Politik-Wirtschaft" }]
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
      "/api/learning/courses/course-1/units/unit-1/modules/module-7?include=materials,tasks"
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
      jsonResponse({ id: "submission-2", intent: "submit", analysis_status: "completed", created_at: "2026-04-07T12:00:00+00:00" }, 201)
    );

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

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/learning/courses/course-1/tasks/task-1/submissions/finalize",
      expect.objectContaining({
        method: "POST",
        includeSameOrigin: true
      })
    );
    expect(result).toEqual({
      finalizedTaskId: "task-1",
      finalizedSubmission: {
        id: "submission-2",
        intent: "submit",
        analysis_status: "completed",
        created_at: "2026-04-07T12:00:00+00:00"
      },
      message: "submitted"
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
});
