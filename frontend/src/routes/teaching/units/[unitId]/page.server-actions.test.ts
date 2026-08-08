import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/api", () => ({
  backendRequest: vi.fn(),
  requireBackendJson: vi.fn()
}));

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/teaching/units/unit-1"),
  requireParentSpaceBootstrap: vi.fn()
}));

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { actions } from "./+page.server";

const backendRequestMock = vi.mocked(backendRequest);
const requireBackendJsonMock = vi.mocked(requireBackendJson);

const modularWorkspace = {
  graph: {
    kind: "modular",
    phases: [
      {
        id: "phase-1",
        title: "Start",
        position: 1,
        modules: [
          { id: "module-1", title: "Einstieg", phase_id: "phase-1", materials_count: 0, tasks_count: 0 },
          { id: "module-2", title: "Vertiefung", phase_id: "phase-1", materials_count: 0, tasks_count: 0 }
        ]
      }
    ],
    edges: []
  }
};

function requestWithFormData(formData: FormData): Request {
  return { formData: async () => formData } as unknown as Request;
}

function actionInput(action: keyof typeof actions, formData: FormData) {
  return {
    fetch: vi.fn() as unknown as typeof fetch,
    cookies: {},
    params: { unitId: "unit-1" },
    request: requestWithFormData(formData),
    url: new URL(`https://app.localhost/teaching/units/unit-1?/${action}`)
  } as never;
}

describe("teacher unit graph server actions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes the selected phase as contextual creation anchor", async () => {
    backendRequestMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "phase-new" }), {
        status: 201,
        headers: { "content-type": "application/json" }
      })
    );
    const form = new FormData();
    form.set("title", "Vertiefung");
    form.set("after_phase_id", "phase-1");

    const result = await actions.createPhase(actionInput("createPhase", form));

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/teaching/units/unit-1/phases",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "Vertiefung", after_phase_id: "phase-1" })
      })
    );
    expect(result).toMatchObject({
      createPhase: {
        ok: true,
        next: { phase: "phase-new", quick: null, panel: "phase-properties", "create-phase": null }
      }
    });
  });

  it.each([
    ["deletePhase", "phase_id", "phase-1"],
    ["deleteModule", "module_id", "module-1"]
  ] as const)("rejects %s without explicit confirmation", async (actionName, fieldName, id) => {
    const form = new FormData();
    form.set(fieldName, id);

    const result = await actions[actionName](actionInput(actionName, form));

    expect(result).toMatchObject({
      status: 400,
      data: {
        [actionName]: {
          error: "Bitte bestätige die endgültige Löschung.",
          values: { [fieldName]: id }
        }
      }
    });
    expect(backendRequestMock).not.toHaveBeenCalled();
  });

  it("keeps the neighbouring module selected after confirmed deletion", async () => {
    requireBackendJsonMock.mockResolvedValueOnce(modularWorkspace as never);
    backendRequestMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const form = new FormData();
    form.set("module_id", "module-1");
    form.set("confirmed", "1");

    const result = await actions.deleteModule(actionInput("deleteModule", form));

    expect(result).toMatchObject({
      deleteModule: {
        ok: true,
        next: {
          module: "module-2",
          phase: null,
          quick: null,
          panel: null,
          edgeFrom: null,
          edgeTo: null
        }
      }
    });
    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/teaching/units/unit-1/modules/module-1",
      expect.objectContaining({ method: "DELETE", includeSameOrigin: true })
    );
  });
});
