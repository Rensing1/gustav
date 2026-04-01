import { fail } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, buildApiUrl, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherUnitNodeEditorView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

function editorHref(unitId: string, nodeId: string): string {
  return `/api/teaching/views/units/${encodeURIComponent(unitId)}/nodes/${encodeURIComponent(nodeId)}/editor`;
}

type EditorActionSuccess = {
  ok: true;
  message: string;
  editor: TeacherUnitNodeEditorView;
  material_id?: string;
  task_id?: string;
};

type UploadIntentResponse = {
  intent_id: string;
  url: string;
  headers: Record<string, string>;
};

type UploadPutResponse = {
  sha256?: string;
  size_bytes?: number;
};

const INVALID_NUMBER = Symbol("invalid_number");
const INVALID_DATETIME = Symbol("invalid_datetime");

function asText(entry: FormDataEntryValue | null): string {
  return typeof entry === "string" ? entry.trim() : "";
}

function asBody(entry: FormDataEntryValue | null): string {
  return typeof entry === "string" ? entry : "";
}

function parseCriteriaText(raw: string): string[] {
  return raw
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 10);
}

function parseOptionalPositiveInt(raw: string): number | null | typeof INVALID_NUMBER {
  if (!raw.trim()) {
    return null;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isInteger(parsed) || parsed < 1) {
    return INVALID_NUMBER;
  }
  return parsed;
}

function parseOptionalDateTime(raw: string): string | null | typeof INVALID_DATETIME {
  if (!raw.trim()) {
    return null;
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.valueOf())) {
    return INVALID_DATETIME;
  }
  return parsed.toISOString();
}

async function readEditor(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  unitId: string,
  nodeId: string
): Promise<TeacherUnitNodeEditorView> {
  return await requireBackendJson<TeacherUnitNodeEditorView>(fetchFn, cookies, editorHref(unitId, nodeId));
}

async function success(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  unitId: string,
  nodeId: string,
  message: string,
  extra?: Partial<EditorActionSuccess>
): Promise<EditorActionSuccess> {
  return {
    ok: true,
    message,
    editor: await readEditor(fetchFn, cookies, unitId, nodeId),
    ...extra
  };
}

function sectionIdForEditor(editor: TeacherUnitNodeEditorView): string {
  return editor.node.backing_section_id ?? editor.node.id;
}

function reorderIds(
  ids: string[],
  targetId: string,
  direction: "up" | "down"
): string[] {
  const currentIndex = ids.indexOf(targetId);
  if (currentIndex === -1) {
    return ids;
  }
  const nextIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
  if (nextIndex < 0 || nextIndex >= ids.length) {
    return ids;
  }
  const reordered = [...ids];
  [reordered[currentIndex], reordered[nextIndex]] = [reordered[nextIndex], reordered[currentIndex]];
  return reordered;
}

async function uploadFileMaterial(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  unitId: string,
  sectionId: string,
  options: {
    title: string;
    altText: string | null;
    uploadFile: File;
  }
): Promise<Response> {
  const mimeType = String(options.uploadFile.type || "").trim().toLowerCase() || "application/octet-stream";
  const intent = await requireBackendJson<UploadIntentResponse>(
    fetchFn,
    cookies,
    `/api/teaching/units/${encodeURIComponent(unitId)}/sections/${encodeURIComponent(sectionId)}/materials/upload-intents`,
    {
      method: "POST",
      includeSameOrigin: true,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        filename: options.uploadFile.name || "material.bin",
        mime_type: mimeType,
        size_bytes: options.uploadFile.size
      })
    }
  );

  const uploadUrl = intent.url.startsWith("http")
    ? intent.url
    : new URL(intent.url, buildApiUrl("/")).toString();

  const uploadResponse = await fetch(uploadUrl, {
    method: "PUT",
    headers: intent.headers,
    body: options.uploadFile
  });

  if (!uploadResponse.ok) {
    throw new Error("upload_failed");
  }

  const uploadResult = (await uploadResponse.json().catch(() => null)) as UploadPutResponse | null;
  if (!uploadResult?.sha256) {
    throw new Error("upload_failed");
  }

  return await backendRequest(
    fetchFn,
    cookies,
    `/api/teaching/units/${encodeURIComponent(unitId)}/sections/${encodeURIComponent(sectionId)}/materials/finalize`,
    {
      method: "POST",
      includeSameOrigin: true,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        intent_id: intent.intent_id,
        title: options.title,
        sha256: uploadResult.sha256,
        alt_text: options.altText
      })
    }
  );
}

function taskPayloadFromForm(
  formData: FormData,
  options: {
    allowImplicitInstructionForH5P: boolean;
  }
):
  | { ok: true; payload: Record<string, unknown>; values: Record<string, string> }
  | { ok: false; error: string; values: Record<string, string> } {
  const taskKind = asText(formData.get("task_kind")) || "native";
  const instructionMdRaw = asBody(formData.get("instruction_md"));
  const instructionMd = instructionMdRaw.trim();
  const criteriaText = asBody(formData.get("criteria_text"));
  const teacherContextMdRaw = asBody(formData.get("teacher_context_md"));
  const dueAtRaw = asText(formData.get("due_at"));
  const maxAttemptsRaw = asText(formData.get("max_attempts"));
  const h5pContentId = asText(formData.get("h5p_content_id"));

  const values = {
    task_kind: taskKind,
    instruction_md: instructionMdRaw,
    criteria_text: criteriaText,
    teacher_context_md: teacherContextMdRaw,
    due_at: dueAtRaw,
    max_attempts: maxAttemptsRaw,
    h5p_content_id: h5pContentId
  };

  if (taskKind !== "h5p" && !instructionMd) {
    return { ok: false, error: "Bitte gib eine Aufgabenstellung ein.", values };
  }

  const dueAt = parseOptionalDateTime(dueAtRaw);
  if (dueAt === INVALID_DATETIME) {
    return { ok: false, error: "Bitte gib ein gültiges Fälligkeitsdatum ein.", values };
  }

  const maxAttempts = parseOptionalPositiveInt(maxAttemptsRaw);
  if (maxAttempts === INVALID_NUMBER) {
    return { ok: false, error: "Bitte gib eine gültige Anzahl an Versuchen ein.", values };
  }

  const payload: Record<string, unknown> = {
    instruction_md:
      taskKind === "h5p" && options.allowImplicitInstructionForH5P
        ? instructionMd || "H5P-Aufgabe"
        : instructionMd,
    criteria: taskKind === "h5p" ? [] : parseCriteriaText(criteriaText),
    teacher_context_md: taskKind === "h5p" ? null : teacherContextMdRaw.trim() || null,
    due_at: dueAt,
    max_attempts: maxAttempts
  };

  if (taskKind === "h5p") {
    payload.h5p = { content_id: h5pContentId || null, display_options: {} };
  } else if (taskKind === "visual") {
    payload.visual = {};
  } else if (taskKind === "scratch") {
    payload.scratch = {};
  } else if (taskKind === "calliope") {
    payload.calliope = {};
  }

  return { ok: true, payload, values };
}

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId);

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Lerneinheiten", href: "/teaching/units" },
    { label: editor.unit.title, href: `/teaching/units/${params.unitId}` }
  ];

  return {
    breadcrumbs,
    hidePageHeading: true,
    pageTitle: editor.node.editor_title,
    editor
  };
};

export const actions: Actions = {
  saveNode: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const kind = asText(formData.get("kind"));
    const title = asText(formData.get("title"));
    const requiredPrereqCountRaw = asText(formData.get("required_prereq_count"));

    if (!title) {
      return fail(400, {
        saveNode: {
          error: "Bitte gib einen Titel ein.",
          values: { title, required_prereq_count: requiredPrereqCountRaw }
        }
      });
    }

    let path = `/api/teaching/units/${params.unitId}/sections/${params.nodeId}`;
    let payload: Record<string, unknown> = { title };

    if (kind === "module") {
      const requiredPrereqCount = Number.parseInt(requiredPrereqCountRaw, 10);
      if (!Number.isInteger(requiredPrereqCount) || requiredPrereqCount < 0) {
        return fail(400, {
          saveNode: {
            error: "Bitte gib eine gültige Freischaltung ein.",
            values: { title, required_prereq_count: requiredPrereqCountRaw }
          }
        });
      }
      path = `/api/teaching/units/${params.unitId}/modules/${params.nodeId}`;
      payload = { title, required_prereq_count: requiredPrereqCount };
    }

    const response = await backendRequest(fetch, cookies, path, {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        saveNode: {
          error: "Der Knoten konnte nicht gespeichert werden.",
          values: { title, required_prereq_count: requiredPrereqCountRaw }
        }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "Knoten gespeichert.");
  },

  saveMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const materialId = asText(formData.get("material_id"));
    const title = asText(formData.get("title"));
    const kind = asText(formData.get("kind")) || "markdown";
    const bodyMd = asBody(formData.get("body_md"));
    const altText = asBody(formData.get("alt_text")).trim() || null;

    if (!sectionId || !materialId || !title) {
      return fail(400, {
        saveMaterial: {
          error: "Bitte gib einen gültigen Titel für das Material ein.",
          material_id: materialId,
          values: { title, body_md: bodyMd, alt_text: altText ?? "" }
        }
      });
    }

    const payload: Record<string, unknown> = { title };
    if (kind === "markdown") {
      payload.body_md = bodyMd;
    } else {
      payload.alt_text = altText;
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/${materialId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
        headers: { "content-type": "application/json" },
        includeSameOrigin: true
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        saveMaterial: {
          error: "Das Material konnte nicht gespeichert werden.",
          material_id: materialId,
          values: { title, body_md: bodyMd, alt_text: altText ?? "" }
        }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "Material gespeichert.", {
      material_id: materialId
    });
  },

  createMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const materialKind = asText(formData.get("material_kind")) || "markdown";
    const title = asText(formData.get("title"));
    const bodyMd = asBody(formData.get("body_md"));
    const altText = asBody(formData.get("alt_text")).trim() || null;
    const fileEntry = formData.get("upload_file");
    const uploadFile = fileEntry instanceof File && fileEntry.size > 0 ? fileEntry : null;

    const values = {
      material_kind: materialKind,
      title,
      body_md: bodyMd,
      alt_text: altText ?? ""
    };

    if (!sectionId || !title) {
      return fail(400, {
        createMaterial: {
          error: "Bitte gib einen Titel für das Material ein.",
          values
        }
      });
    }

    let response: Response;
    if (materialKind === "file") {
      if (!uploadFile) {
        return fail(400, {
          createMaterial: {
            error: "Bitte wähle eine Datei aus.",
            values
          }
        });
      }

      try {
        response = await uploadFileMaterial(fetch, cookies, params.unitId, sectionId, {
          title,
          altText,
          uploadFile
        });
      } catch {
        return fail(502, {
          createMaterial: {
            error: "Die Datei konnte nicht hochgeladen werden.",
            values
          }
        });
      }
    } else {
      if (!bodyMd.trim()) {
        return fail(400, {
          createMaterial: {
            error: "Bitte gib Titel und Inhalt für das Material ein.",
            values
          }
        });
      }

      response = await backendRequest(
        fetch,
        cookies,
        `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials`,
        {
          method: "POST",
          body: JSON.stringify({ title, body_md: bodyMd }),
          headers: { "content-type": "application/json" },
          includeSameOrigin: true
        }
      );
    }

    if (!response.ok) {
      return fail(response.status, {
        createMaterial: {
          error: "Das Material konnte nicht angelegt werden.",
          values
        }
      });
    }

    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId);
    const createdMaterial = editor.materials.at(-1);
    return {
      ok: true,
      message: "Material angelegt.",
      editor,
      material_id: createdMaterial?.id
    };
  },

  deleteMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const materialId = asText(formData.get("material_id"));

    if (!sectionId || !materialId) {
      return fail(400, { deleteMaterial: { error: "Es wurde kein Material ausgewählt." } });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/${materialId}`,
      {
        method: "DELETE",
        includeSameOrigin: true
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        deleteMaterial: { error: "Das Material konnte nicht gelöscht werden." }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "Material gelöscht.");
  },

  reorderMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const materialId = asText(formData.get("material_id"));
    const direction = asText(formData.get("direction")) === "down" ? "down" : "up";
    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId);
    const sectionId = sectionIdForEditor(editor);
    const orderedIds = editor.materials.map((item) => item.id);
    const nextIds = reorderIds(orderedIds, materialId, direction);

    if (nextIds.join(",") === orderedIds.join(",")) {
      return {
        ok: true,
        message: "",
        editor,
        material_id: materialId
      };
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/reorder`,
      {
        method: "POST",
        includeSameOrigin: true,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ material_ids: nextIds })
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        reorderMaterial: { error: "Die Materialien konnten nicht neu geordnet werden." }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "", {
      material_id: materialId
    });
  },

  saveTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const taskId = asText(formData.get("task_id"));
    const parsed = taskPayloadFromForm(formData, { allowImplicitInstructionForH5P: true });

    if (!sectionId || !taskId) {
      return fail(400, {
        saveTask: {
          error: "Es wurde keine Aufgabe ausgewählt.",
          task_id: taskId,
          values: parsed.ok ? parsed.values : parsed.values
        }
      });
    }

    if (!parsed.ok) {
      return fail(400, {
        saveTask: {
          error: parsed.error,
          task_id: taskId,
          values: parsed.values
        }
      });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/${taskId}`,
      {
        method: "PATCH",
        body: JSON.stringify(parsed.payload),
        headers: { "content-type": "application/json" },
        includeSameOrigin: true
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        saveTask: {
          error: "Die Aufgabe konnte nicht gespeichert werden.",
          task_id: taskId,
          values: parsed.values
        }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "Aufgabe gespeichert.", {
      task_id: taskId
    });
  },

  createTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const parsed = taskPayloadFromForm(formData, { allowImplicitInstructionForH5P: true });

    if (!sectionId) {
      return fail(400, {
        createTask: {
          error: "Es wurde kein Abschnitt für die Aufgabe gefunden.",
          values: parsed.ok ? parsed.values : parsed.values
        }
      });
    }

    if (!parsed.ok) {
      return fail(400, {
        createTask: {
          error: parsed.error,
          values: parsed.values
        }
      });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks`,
      {
        method: "POST",
        body: JSON.stringify(parsed.payload),
        headers: { "content-type": "application/json" },
        includeSameOrigin: true
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        createTask: {
          error: "Die Aufgabe konnte nicht angelegt werden.",
          values: parsed.values
        }
      });
    }

    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId);
    const createdTask = editor.tasks.at(-1);
    return {
      ok: true,
      message: "Aufgabe angelegt.",
      editor,
      task_id: createdTask?.id
    };
  },

  deleteTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const taskId = asText(formData.get("task_id"));

    if (!sectionId || !taskId) {
      return fail(400, { deleteTask: { error: "Es wurde keine Aufgabe ausgewählt." } });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/${taskId}`,
      {
        method: "DELETE",
        includeSameOrigin: true
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        deleteTask: { error: "Die Aufgabe konnte nicht gelöscht werden." }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "Aufgabe gelöscht.");
  },

  reorderTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const taskId = asText(formData.get("task_id"));
    const direction = asText(formData.get("direction")) === "down" ? "down" : "up";
    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId);
    const sectionId = sectionIdForEditor(editor);
    const orderedIds = editor.tasks.map((item) => item.id);
    const nextIds = reorderIds(orderedIds, taskId, direction);

    if (nextIds.join(",") === orderedIds.join(",")) {
      return {
        ok: true,
        message: "",
        editor,
        task_id: taskId
      };
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/reorder`,
      {
        method: "POST",
        includeSameOrigin: true,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ task_ids: nextIds })
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        reorderTask: { error: "Die Aufgaben konnten nicht neu geordnet werden." }
      });
    }

    return await success(fetch, cookies, params.unitId, params.nodeId, "", {
      task_id: taskId
    });
  }
};
