import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/api", () => ({
  backendRequest: vi.fn(),
  buildApiUrl: vi.fn((path: string) => `https://app.localhost${path}`),
  requireBackendJson: vi.fn()
}));

vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/teaching/units/unit-1/nodes/node-1"),
  requireParentSpaceBootstrap: vi.fn(async () => ({
    user: { sub: "teacher-1", name: "Felix", roles: ["teacher"] }
  }))
}));

import { actions, __testables, load } from "./+page.server";
import { backendRequest, requireBackendJson } from "$lib/server/api";

const backendRequestMock = vi.mocked(backendRequest);
const requireBackendJsonMock = vi.mocked(requireBackendJson);

function requestWithFormData(formData: FormData): Parameters<typeof actions.createMaterial>[0]["request"] {
  return {
    formData: async () => formData
  } as Parameters<typeof actions.createMaterial>[0]["request"];
}

describe("teacher node editor server helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const editor = {
      user: {
        sub: "teacher-1",
        name: "Felix",
        role: "teacher",
        roles: ["teacher"]
      },
      unit: {
        id: "unit-1",
        title: "Einheit",
        unit_type: "modular",
        edit_href: "/teaching/units/unit-1"
      },
      node: {
        id: "node-1",
        kind: "module",
        title: "Orientierung",
        editor_title: "Orientierung",
        backing_section_id: "section-1"
      },
      settings: {
        kind: "module",
        required_prereq_count: 0
      },
      materials: [],
      tasks: []
    };
    requireBackendJsonMock.mockImplementation(async (_fetch, _cookies, href) => {
      if (String(href).includes("/workspace")) {
        return {
          graph: {
            kind: "modular",
            phases: [
              {
                id: "phase-1",
                title: "Phase",
                position: 1,
                modules: [
                  {
                    id: "node-1",
                    title: "Orientierung",
                    phase_id: "phase-1",
                    materials_count: 0,
                    tasks_count: 0
                  }
                ]
              }
            ],
            edges: []
          }
        } as never;
      }
      return editor as never;
    });
  });

  it("does not load modular deletion context for a linear section", async () => {
    requireBackendJsonMock.mockResolvedValueOnce({
      user: { sub: "teacher-1", name: "Felix", role: "teacher", roles: ["teacher"] },
      unit: { id: "unit-1", title: "Einheit", unit_type: "linear", edit_href: "/teaching/units/unit-1" },
      node: {
        id: "section-1",
        kind: "section",
        title: "Einstieg",
        editor_title: "Einstieg",
        backing_section_id: "section-1"
      },
      settings: { kind: "section" },
      materials: [],
      tasks: []
    } as never);

    const result = await load({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {},
      params: { unitId: "unit-1", nodeId: "section-1" },
      parent: vi.fn(async () => ({})),
      url: new URL("https://app.localhost/teaching/units/unit-1/nodes/section-1")
    } as never);

    expect(requireBackendJsonMock).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ moduleDeletionImpact: null });
  });

  it("parses repeated criteria fields into a bounded list", () => {
    const formData = new FormData();
    formData.set("task_kind", "native");
    formData.set("instruction_md", "Arbeite den Text durch.");

    for (let index = 0; index < 12; index += 1) {
      formData.append("criteria[]", `Kriterium ${index + 1}`);
    }
    formData.append("criteria[]", "   ");

    const parsed = __testables.taskPayloadFromForm(formData, {
      allowImplicitInstructionForH5P: true
    });

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }
    expect(parsed.payload.criteria).toEqual([
      "Kriterium 1",
      "Kriterium 2",
      "Kriterium 3",
      "Kriterium 4",
      "Kriterium 5",
      "Kriterium 6",
      "Kriterium 7",
      "Kriterium 8",
      "Kriterium 9",
      "Kriterium 10"
    ]);
    expect(parsed.values.criteria_items).toHaveLength(10);
  });

  it("finalizes prepared file uploads instead of uploading server-side", async () => {
    backendRequestMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "material-file-1",
          title: "Arbeitsblatt",
          kind: "file",
          position: 1,
          mime_type: "application/pdf",
          size_bytes: 1024,
          filename_original: "arbeitsblatt.pdf",
          alt_text: "PDF Arbeitsblatt"
        }),
        {
          status: 201,
          headers: { "content-type": "application/json" }
        }
      )
    );

    const form = new FormData();
    form.set("section_id", "section-1");
    form.set("material_kind", "file");
    form.set("title", "Arbeitsblatt");
    form.set("alt_text", "PDF Arbeitsblatt");
    form.set("intent_id", "intent-1");
    form.set("sha256", "a".repeat(64));

    const result = await actions.createMaterial({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.createMaterial>[0]["cookies"],
      params: { unitId: "unit-1", nodeId: "node-1" },
      request: requestWithFormData(form)
    } as Parameters<typeof actions.createMaterial>[0]);

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/teaching/units/unit-1/sections/section-1/materials/finalize",
      expect.objectContaining({
        method: "POST",
        includeSameOrigin: true,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          intent_id: "intent-1",
          title: "Arbeitsblatt",
          sha256: "a".repeat(64),
          alt_text: "PDF Arbeitsblatt"
        })
      })
    );
    expect(result).toMatchObject({
      createMaterial: {
        ok: true,
        message: "Material angelegt.",
        material_id: "material-file-1",
        editor: {
          materials: [
            {
              id: "material-file-1",
              title: "Arbeitsblatt",
              kind: "file"
            }
          ]
        }
      }
    });
  });

  it("merges a created markdown material into the editor when the reread is stale", async () => {
    backendRequestMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "material-md-1",
          title: "Merkblatt",
          kind: "markdown",
          body_md: "Inhalt",
          position: 1
        }),
        {
          status: 201,
          headers: { "content-type": "application/json" }
        }
      )
    );

    const form = new FormData();
    form.set("section_id", "section-1");
    form.set("material_kind", "markdown");
    form.set("title", "Merkblatt");
    form.set("body_md", "Inhalt");

    const result = await actions.createMaterial({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.createMaterial>[0]["cookies"],
      params: { unitId: "unit-1", nodeId: "node-1" },
      request: requestWithFormData(form)
    } as Parameters<typeof actions.createMaterial>[0]);

    expect(result).toMatchObject({
      createMaterial: {
        ok: true,
        material_id: "material-md-1",
        editor: {
          materials: [
            {
              id: "material-md-1",
              title: "Merkblatt",
              kind: "markdown",
              body_md: "Inhalt"
            }
          ]
        }
      }
    });
  });

  it("returns namespaced success for saveTask so the page can react consistently", async () => {
    backendRequestMock.mockResolvedValueOnce(new Response(null, { status: 200 }));

    const form = new FormData();
    form.set("section_id", "section-1");
    form.set("task_id", "task-1");
    form.set("task_kind", "native");
    form.set("instruction_md", "Bearbeite die Aufgabe.");

    const result = await actions.saveTask({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.saveTask>[0]["cookies"],
      params: { unitId: "unit-1", nodeId: "node-1" },
      request: requestWithFormData(form)
    } as Parameters<typeof actions.saveTask>[0]);

    expect(result).toMatchObject({
      saveTask: {
        ok: true,
        message: "Aufgabe gespeichert.",
        task_id: "task-1",
        editor: {
          node: {
            id: "node-1"
          }
        }
      }
    });
  });

  it("requires explicit confirmation before deleting a module", async () => {
    const form = new FormData();

    const result = await actions.deleteModule({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.deleteModule>[0]["cookies"],
      params: { unitId: "unit-1", nodeId: "node-1" },
      request: requestWithFormData(form)
    } as Parameters<typeof actions.deleteModule>[0]);

    expect(result).toMatchObject({
      status: 400,
      data: {
        deleteModule: {
          error: "Bitte bestätige die endgültige Löschung."
        }
      }
    });
    expect(backendRequestMock).not.toHaveBeenCalled();
  });

  it("deletes a confirmed module and returns to its graph", async () => {
    backendRequestMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const form = new FormData();
    form.set("confirmed", "1");

    await expect(
      actions.deleteModule({
        fetch: vi.fn() as unknown as typeof fetch,
        cookies: {} as Parameters<typeof actions.deleteModule>[0]["cookies"],
        params: { unitId: "unit-1", nodeId: "node-1" },
        request: requestWithFormData(form)
      } as Parameters<typeof actions.deleteModule>[0])
    ).rejects.toMatchObject({ status: 303, location: "/teaching/units/unit-1?phase=phase-1&quick=1" });

    expect(backendRequestMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.anything(),
      "/api/teaching/units/unit-1/modules/node-1",
      expect.objectContaining({ method: "DELETE", includeSameOrigin: true })
    );
  });

  it("creates Filius tasks with the Filius marker payload", () => {
    const formData = new FormData();
    formData.set("task_kind", "filius");
    formData.set("instruction_md", "Analysiere das Netzwerk.");
    formData.append("criteria[]", "DNS ist korrekt eingerichtet");
    formData.set("teacher_context_md", "Achte auf IP-Adressierung.");

    const parsed = __testables.taskPayloadFromForm(formData, {
      allowImplicitInstructionForH5P: true
    });

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }
    expect(parsed.payload).toMatchObject({
      instruction_md: "Analysiere das Netzwerk.",
      criteria: ["DNS ist korrekt eingerichtet"],
      teacher_context_md: "Achte auf IP-Adressierung.",
      filius: {}
    });
    expect(parsed.payload).not.toHaveProperty("h5p");
    expect(parsed.payload).not.toHaveProperty("visual");
    expect(parsed.payload).not.toHaveProperty("scratch");
    expect(parsed.payload).not.toHaveProperty("calliope");
  });

  it("creates dialog tasks with every configured authoring field", () => {
    const formData = new FormData();
    formData.set("task_kind", "dialog");
    formData.set("instruction_md", "Führe einen prüfenden Dialog.");
    formData.append("criteria[]", "Antworten sind begründet");
    formData.set("teacher_context_md", "Interner Fachkontext.");
    formData.set("dialog_partner_name", "Dr. Dialog");
    formData.set("dialog_partner_description_md", "Eine sichtbare Kurzbeschreibung.");
    formData.set("dialog_role_md", "Stelle präzise Rückfragen.");
    formData.set("dialog_learning_goal_md", "Argumente begründet prüfen.");
    formData.set("dialog_opening_message_md", "Welche Position vertrittst du?");
    formData.set("dialog_response_mode", "hybrid");
    formData.set("dialog_max_rounds", "7");
    formData.set("dialog_closing_prompt_md", "Fasse dein Ergebnis zusammen.");

    const parsed = __testables.taskPayloadFromForm(formData, {
      allowImplicitInstructionForH5P: true
    });

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }
    expect(parsed.payload).toEqual({
      instruction_md: "Führe einen prüfenden Dialog.",
      criteria: ["Antworten sind begründet"],
      teacher_context_md: "Interner Fachkontext.",
      due_at: null,
      max_attempts: null,
      dialog: {
        partner_name: "Dr. Dialog",
        partner_description_md: "Eine sichtbare Kurzbeschreibung.",
        role_md: "Stelle präzise Rückfragen.",
        learning_goal_md: "Argumente begründet prüfen.",
        opening_message_md: "Welche Position vertrittst du?",
        response_mode: "hybrid",
        max_rounds: 7,
        closing_prompt_md: "Fasse dein Ergebnis zusammen."
      }
    });
  });

  it("rejects raw file posts without prepared upload metadata", async () => {
    const form = new FormData();
    form.set("section_id", "section-1");
    form.set("material_kind", "file");
    form.set("title", "Arbeitsblatt");
    form.set("upload_file", new File(["pdf"], "arbeitsblatt.pdf", { type: "application/pdf" }));

    const result = await actions.createMaterial({
      fetch: vi.fn() as unknown as typeof fetch,
      cookies: {} as Parameters<typeof actions.createMaterial>[0]["cookies"],
      params: { unitId: "unit-1", nodeId: "node-1" },
      request: requestWithFormData(form)
    } as Parameters<typeof actions.createMaterial>[0]);

    expect(result).toMatchObject({
      status: 400,
      data: {
        createMaterial: {
          error: "Datei-Uploads benötigen aktiviertes JavaScript."
        }
      }
    });
    expect(backendRequestMock).not.toHaveBeenCalled();
  });
});
