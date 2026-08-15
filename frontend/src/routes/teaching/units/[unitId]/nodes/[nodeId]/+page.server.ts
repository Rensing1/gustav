import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import {
  graphDeletionFallback,
  graphDeletionImpact
} from "$lib/teacher-unit-workspace/graph-deletion-impact";
import { parseContentSelection } from "$lib/teacher-node-editor/module-content-state";
import type {
  TeacherUnitNodeEditorMaterial,
  TeacherUnitNodeEditorView,
  TeacherUnitWorkspaceView
} from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

function editorHref(unitId: string, nodeId: string): string {
  return `/api/teaching/views/units/${encodeURIComponent(unitId)}/nodes/${encodeURIComponent(nodeId)}/editor`;
}

function workspaceHref(unitId: string, nodeId: string): string {
  return `/api/teaching/views/units/${encodeURIComponent(unitId)}/workspace?module_id=${encodeURIComponent(nodeId)}`;
}

function actionAuthRedirectPath(url: URL | undefined): string {
  return url ? currentPath(url) : "/";
}

type EditorActionSuccess = {
  ok: true;
  message: string;
  editor: TeacherUnitNodeEditorView;
  material_id?: string;
  task_id?: string;
};

type EditorActionName =
  | "saveNode"
  | "saveMaterial"
  | "createMaterial"
  | "deleteMaterial"
  | "reorderMaterial"
  | "saveTask"
  | "createTask"
  | "deleteTask"
  | "reorderTask"
  | "deleteModule";

const INVALID_NUMBER = Symbol("invalid_number");
const INVALID_DATETIME = Symbol("invalid_datetime");

function asText(entry: FormDataEntryValue | null): string {
  return typeof entry === "string" ? entry.trim() : "";
}

function asBody(entry: FormDataEntryValue | null): string {
  return typeof entry === "string" ? entry : "";
}

function normalizeCriteriaItems(values: string[]): string[] {
  return values
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 10);
}

function readCriteriaItems(formData: FormData): string[] {
  const repeatedEntries = formData.getAll("criteria[]").filter((entry): entry is string => typeof entry === "string");
  if (repeatedEntries.length > 0) {
    return normalizeCriteriaItems(repeatedEntries);
  }
  return normalizeCriteriaItems(asBody(formData.get("criteria_text")).split("\n"));
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
  nodeId: string,
  authRedirectPath: string
): Promise<TeacherUnitNodeEditorView> {
  return await requireBackendJson<TeacherUnitNodeEditorView>(fetchFn, cookies, editorHref(unitId, nodeId), {
    authRedirectPath
  });
}

async function success<K extends EditorActionName>(
  action: K,
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  unitId: string,
  nodeId: string,
  authRedirectPath: string,
  message: string,
  extra?: Partial<EditorActionSuccess>
): Promise<Record<K, EditorActionSuccess>> {
  return {
    [action]: {
      ok: true,
      message,
      editor: await readEditor(fetchFn, cookies, unitId, nodeId, authRedirectPath),
      ...extra
    }
  } as Record<K, EditorActionSuccess>;
}

async function readCreatedMaterial(response: Response): Promise<TeacherUnitNodeEditorMaterial | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return null;
  }

  const payload = (await response.clone().json().catch(() => null)) as TeacherUnitNodeEditorMaterial | null;
  if (!payload || typeof payload !== "object" || typeof payload.id !== "string") {
    return null;
  }
  return payload;
}

function mergeCreatedMaterialIntoEditor(
  editor: TeacherUnitNodeEditorView,
  createdMaterial: TeacherUnitNodeEditorMaterial | null
): TeacherUnitNodeEditorView {
  if (!createdMaterial) {
    return editor;
  }

  if (editor.materials.some((material) => material.id === createdMaterial.id)) {
    return editor;
  }

  const mergedMaterials = [...editor.materials, createdMaterial].sort((left, right) => left.position - right.position);
  return {
    ...editor,
    materials: mergedMaterials
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

function moveIdBefore(ids: string[], movedId: string, beforeId: string): string[] {
  if (movedId === beforeId || !ids.includes(movedId) || !ids.includes(beforeId)) {
    return ids;
  }
  const reordered = ids.filter((id) => id !== movedId);
  reordered.splice(reordered.indexOf(beforeId), 0, movedId);
  return reordered;
}

async function finalizePreparedFileMaterial(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  unitId: string,
  sectionId: string,
  options: {
    kind: "file" | "simulation";
    title: string;
    altText: string | null;
    bodyMd: string;
    intentId: string;
    sha256: string;
    authRedirectPath: string;
  }
): Promise<Response> {
  return await backendRequest(
    fetchFn,
    cookies,
    `/api/teaching/units/${encodeURIComponent(unitId)}/sections/${encodeURIComponent(sectionId)}/materials/finalize`,
    {
      method: "POST",
      includeSameOrigin: true,
      headers: { "content-type": "application/json" },
      authRedirectPath: options.authRedirectPath,
      body: JSON.stringify({
        intent_id: options.intentId,
        title: options.title,
        sha256: options.sha256,
        ...(options.kind === "simulation"
          ? { body_md: options.bodyMd }
          : { alt_text: options.altText })
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
  | { ok: true; payload: Record<string, unknown>; values: Record<string, unknown> }
  | { ok: false; error: string; values: Record<string, unknown> } {
  const taskKind = asText(formData.get("task_kind")) || "native";
  const instructionMdRaw = asBody(formData.get("instruction_md"));
  const instructionMd = instructionMdRaw.trim();
  const criteriaItems = readCriteriaItems(formData);
  const teacherContextMdRaw = asBody(formData.get("teacher_context_md"));
  const modelSolutionMdRaw = asBody(formData.get("model_solution_md"));
  const practiceModule = asText(formData.get("module_kind")) === "practice";
  const dueAtRaw = asText(formData.get("due_at"));
  const maxAttemptsRaw = asText(formData.get("max_attempts"));
  const h5pContentId = asText(formData.get("h5p_content_id"));
  const dialogMaxRoundsRaw = asText(formData.get("dialog_max_rounds")) || "8";
  const dialogMaxRounds = Number.parseInt(dialogMaxRoundsRaw, 10);

  const values = {
    task_kind: taskKind,
    instruction_md: instructionMdRaw,
    criteria_items: criteriaItems,
    teacher_context_md: teacherContextMdRaw,
    model_solution_md: modelSolutionMdRaw,
    due_at: dueAtRaw,
    max_attempts: maxAttemptsRaw,
    h5p_content_id: h5pContentId,
    dialog_partner_name: asBody(formData.get("dialog_partner_name")),
    dialog_partner_description_md: asBody(formData.get("dialog_partner_description_md")),
    dialog_role_md: asBody(formData.get("dialog_role_md")),
    dialog_learning_goal_md: asBody(formData.get("dialog_learning_goal_md")),
    dialog_opening_message_md: asBody(formData.get("dialog_opening_message_md")),
    dialog_response_mode: asText(formData.get("dialog_response_mode")) || "free_text",
    dialog_max_rounds: dialogMaxRoundsRaw,
    dialog_closing_prompt_md: asBody(formData.get("dialog_closing_prompt_md"))
  };

  if (taskKind !== "h5p" && !instructionMd) {
    return { ok: false, error: "Bitte gib eine Aufgabenstellung ein.", values };
  }
  if (practiceModule && !["native", "h5p"].includes(taskKind)) {
    return { ok: false, error: "Übungsmodule unterstützen nur normale Aufgaben und H5P.", values };
  }
  if (
    practiceModule &&
    taskKind === "native" &&
    (!criteriaItems.length || !teacherContextMdRaw.trim() || !modelSolutionMdRaw.trim())
  ) {
    return {
      ok: false,
      error: "Normale Übungsaufgaben benötigen mindestens ein Kriterium, Lehrkraft-Kontext und Musterlösung.",
      values
    };
  }

  const dueAt = parseOptionalDateTime(dueAtRaw);
  if (dueAt === INVALID_DATETIME) {
    return { ok: false, error: "Bitte gib ein gültiges Fälligkeitsdatum ein.", values };
  }

  const maxAttempts = parseOptionalPositiveInt(maxAttemptsRaw);
  if (maxAttempts === INVALID_NUMBER) {
    return { ok: false, error: "Bitte gib eine gültige Anzahl an Versuchen ein.", values };
  }
  if (taskKind === "dialog" && (!Number.isInteger(dialogMaxRounds) || dialogMaxRounds < 1 || dialogMaxRounds > 12)) {
    return { ok: false, error: "Bitte wähle zwischen 1 und 12 Dialogrunden.", values };
  }

  const payload: Record<string, unknown> = {
    instruction_md:
      taskKind === "h5p" && options.allowImplicitInstructionForH5P
        ? instructionMd || "H5P-Aufgabe"
        : instructionMd,
    criteria: taskKind === "h5p" ? [] : criteriaItems,
    teacher_context_md: taskKind === "h5p" ? null : teacherContextMdRaw.trim() || null,
    model_solution_md: taskKind === "h5p" ? null : modelSolutionMdRaw.trim() || null,
    due_at: practiceModule ? null : dueAt,
    max_attempts: practiceModule ? null : maxAttempts
  };

  if (taskKind === "h5p") {
    payload.h5p = { content_id: h5pContentId || null, display_options: {} };
  } else if (taskKind === "visual") {
    payload.visual = {};
  } else if (taskKind === "scratch") {
    payload.scratch = {};
  } else if (taskKind === "calliope") {
    payload.calliope = {};
  } else if (taskKind === "filius") {
    payload.filius = {};
  } else if (taskKind === "dialog") {
    payload.dialog = {
      partner_name: asText(formData.get("dialog_partner_name")),
      partner_description_md: asBody(formData.get("dialog_partner_description_md")).trim(),
      role_md: asBody(formData.get("dialog_role_md")).trim(),
      learning_goal_md: asBody(formData.get("dialog_learning_goal_md")).trim(),
      opening_message_md: asBody(formData.get("dialog_opening_message_md")).trim(),
      response_mode: asText(formData.get("dialog_response_mode")) || "free_text",
      max_rounds: dialogMaxRounds,
      closing_prompt_md: asBody(formData.get("dialog_closing_prompt_md")).trim() || null
    };
  }

  return { ok: true, payload, values };
}

export const __testables = {
  moveIdBefore,
  normalizeCriteriaItems,
  readCriteriaItems,
  taskPayloadFromForm
};

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId, authRedirectPath);
  const workspace =
    editor.node.kind === "module"
      ? await requireBackendJson<TeacherUnitWorkspaceView>(
          fetch,
          cookies,
          workspaceHref(params.unitId, params.nodeId),
          { authRedirectPath }
        )
      : null;

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Lerneinheiten", href: "/teaching/units" },
    { label: editor.unit.title, href: `/teaching/units/${params.unitId}` }
  ];

  return {
    breadcrumbs,
    hidePageHeading: true,
    workspaceLayout: editor.node.kind === "module" ? "wide" : "compact",
    pageTitle: editor.node.editor_title,
    editor,
    contentSelection: parseContentSelection(url.searchParams.get("content"), editor),
    incomingPrerequisiteCount:
      editor.node.kind === "module" && workspace?.graph.kind === "modular"
        ? (workspace.graph.edges ?? []).filter((edge) => edge.to === editor.node.id).length
        : 0,
    moduleDeletionImpact:
      editor.node.kind === "module" && workspace
        ? graphDeletionImpact(workspace, { kind: "module", id: editor.node.id })
        : null
  };
};

export const actions: Actions = {
  deleteModule: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const confirmed = asText(formData.get("confirmed"));

    if (confirmed !== "1") {
      return fail(400, { deleteModule: { error: "Bitte bestätige die endgültige Löschung." } });
    }

    const workspace = await requireBackendJson<TeacherUnitWorkspaceView>(
      fetch,
      cookies,
      workspaceHref(params.unitId, params.nodeId),
      { authRedirectPath }
    );
    const fallback = graphDeletionFallback(workspace, { kind: "module", id: params.nodeId });

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/modules/${params.nodeId}`,
      {
        method: "DELETE",
        includeSameOrigin: true,
        authRedirectPath
      }
    );

    if (!response.ok) {
      return fail(response.status, { deleteModule: { error: "Das Modul konnte nicht entfernt werden." } });
    }

    const graphUrl = new URL(`/teaching/units/${params.unitId}`, "https://app.localhost");
    if (fallback?.kind === "module") {
      graphUrl.searchParams.set("module", fallback.id);
    } else if (fallback?.kind === "phase") {
      graphUrl.searchParams.set("phase", fallback.id);
    }
    throw redirect(303, `${graphUrl.pathname}${graphUrl.search}`);
  },

  saveNode: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
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
      includeSameOrigin: true,
      authRedirectPath
    });

    if (!response.ok) {
      return fail(response.status, {
        saveNode: {
          error: "Der Knoten konnte nicht gespeichert werden.",
          values: { title, required_prereq_count: requiredPrereqCountRaw }
        }
      });
    }

    return await success("saveNode", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "Knoten gespeichert.");
  },

  saveMaterial: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
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
    if (kind === "markdown" || kind === "simulation") {
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
        includeSameOrigin: true,
        authRedirectPath
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

    return await success("saveMaterial", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "Material gespeichert.", {
      material_id: materialId
    });
  },

  createMaterial: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const materialKind = asText(formData.get("material_kind")) || "markdown";
    const title = asText(formData.get("title"));
    const bodyMd = asBody(formData.get("body_md"));
    const altText = asBody(formData.get("alt_text")).trim() || null;
    const fileEntry = formData.get("upload_file");
    const uploadFile = fileEntry instanceof File && fileEntry.size > 0 ? fileEntry : null;
    const intentId = asText(formData.get("intent_id"));
    const sha256 = asText(formData.get("sha256")).toLowerCase();

    const values = {
      material_kind: materialKind,
      title,
      body_md: bodyMd,
      alt_text: altText ?? "",
      intent_id: intentId,
      sha256
    };

    if (!sectionId || !title) {
      return fail(400, {
        createMaterial: {
          error: "Bitte gib einen Titel für das Material ein.",
          field: "title",
          values
        }
      });
    }

    let response: Response;
    if (materialKind === "file" || materialKind === "simulation") {
      if (!uploadFile && !intentId && !sha256) {
        return fail(400, {
            createMaterial: {
              error: "Bitte wähle eine Datei aus.",
              field: "upload_file",
              values
          }
        });
      }

      if (!intentId || !sha256) {
        return fail(400, {
            createMaterial: {
              error: "Datei-Uploads benötigen aktiviertes JavaScript.",
              field: "upload_file",
              values
          }
        });
      }

      response = await finalizePreparedFileMaterial(fetch, cookies, params.unitId, sectionId, {
        kind: materialKind,
        title,
        altText: materialKind === "file" ? altText : null,
        bodyMd,
        intentId,
        sha256,
        authRedirectPath
      });
    } else {
      if (!bodyMd.trim()) {
        return fail(400, {
            createMaterial: {
              error: "Bitte gib Titel und Inhalt für das Material ein.",
              field: "body_md",
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
          includeSameOrigin: true,
          authRedirectPath
        }
      );
    }

    if (!response.ok) {
      if (materialKind === "file" || materialKind === "simulation") {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        const detail = payload.detail || "";
        if (detail === "intent_expired") {
          return fail(response.status, {
            createMaterial: {
              error: "Die Upload-Freigabe ist abgelaufen. Bitte wähle die Datei erneut aus.",
              field: "upload_file",
              requires_reupload: true,
              values: {
                ...values,
                intent_id: "",
                sha256: ""
              }
            }
          });
        }
        if (detail === "mime_not_allowed") {
          return fail(response.status, {
            createMaterial: {
              error: materialKind === "simulation"
                ? "Bitte wähle eine selbstständige HTML-Datei aus."
                : "Dateiformat nicht erlaubt. Erlaubt sind PDF, PNG und JPEG.",
              field: "upload_file",
              requires_reupload: true,
              values: {
                ...values,
                intent_id: "",
                sha256: ""
              }
            }
          });
        }
        if (detail === "checksum_mismatch") {
          return fail(response.status, {
            createMaterial: {
              error: "Die Datei konnte nicht bestätigt werden. Bitte wähle sie erneut aus.",
              field: "upload_file",
              requires_reupload: true,
              values: {
                ...values,
                intent_id: "",
                sha256: ""
              }
            }
          });
        }
        if (detail === "invalid_simulation_html" || detail === "simulation_not_self_contained") {
          return fail(response.status, {
            createMaterial: {
              error: detail === "simulation_not_self_contained"
                ? "Die Simulation enthält externe Ressourcen, Navigationen oder Netzwerkzugriffe."
                : "Die HTML-Datei ist keine vollständige, gültige UTF-8-Simulation.",
              field: "upload_file",
              requires_reupload: true,
              values: { ...values, intent_id: "", sha256: "" }
            }
          });
        }
      }
      return fail(response.status, {
        createMaterial: {
          error: "Das Material konnte nicht angelegt werden.",
          values
        }
      });
    }

    const createdMaterial = await readCreatedMaterial(response);
    const editor = mergeCreatedMaterialIntoEditor(
      await readEditor(fetch, cookies, params.unitId, params.nodeId, authRedirectPath),
      createdMaterial
    );

    return {
      createMaterial: {
        ok: true,
        message: "Material angelegt.",
        editor,
        material_id: createdMaterial?.id
      }
    };
  },

  deleteMaterial: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const materialId = asText(formData.get("material_id"));
    const confirmed = asText(formData.get("confirmed"));

    if (!sectionId || !materialId) {
      return fail(400, { deleteMaterial: { error: "Es wurde kein Material ausgewählt." } });
    }
    if (confirmed !== "1") {
      return fail(400, {
        deleteMaterial: { error: "Bitte bestätige, dass du das Material löschen möchtest." }
      });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/${materialId}`,
      {
        method: "DELETE",
        includeSameOrigin: true,
        authRedirectPath
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        deleteMaterial: { error: "Das Material konnte nicht gelöscht werden." }
      });
    }

    return await success("deleteMaterial", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "Material gelöscht.");
  },

  reorderMaterial: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const materialId = asText(formData.get("material_id"));
    const beforeId = asText(formData.get("before_id"));
    const direction = asText(formData.get("direction")) === "down" ? "down" : "up";
    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId, authRedirectPath);
    const sectionId = sectionIdForEditor(editor);
    const orderedIds = editor.materials.map((item) => item.id);
    const nextIds = beforeId ? moveIdBefore(orderedIds, materialId, beforeId) : reorderIds(orderedIds, materialId, direction);

    if (nextIds.join(",") === orderedIds.join(",")) {
      return {
        reorderMaterial: {
          ok: true,
          message: "",
          editor,
          material_id: materialId
        }
      };
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/reorder`,
      {
        method: "POST",
        includeSameOrigin: true,
        authRedirectPath,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ material_ids: nextIds })
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        reorderMaterial: { error: "Die Materialien konnten nicht neu geordnet werden." }
      });
    }

    return await success("reorderMaterial", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "", {
      material_id: materialId
    });
  },

  saveTask: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
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
        includeSameOrigin: true,
        authRedirectPath
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

    return await success("saveTask", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "Aufgabe gespeichert.", {
      task_id: taskId
    });
  },

  createTask: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
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
        includeSameOrigin: true,
        authRedirectPath
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

    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId, authRedirectPath);
    const createdTask = editor.tasks.at(-1);
    return {
      createTask: {
        ok: true,
        message: "Aufgabe angelegt.",
        editor,
        task_id: createdTask?.id
      }
    };
  },

  deleteTask: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const sectionId = asText(formData.get("section_id"));
    const taskId = asText(formData.get("task_id"));
    const confirmed = asText(formData.get("confirmed"));

    if (!sectionId || !taskId) {
      return fail(400, { deleteTask: { error: "Es wurde keine Aufgabe ausgewählt." } });
    }
    if (confirmed !== "1") {
      return fail(400, {
        deleteTask: { error: "Bitte bestätige, dass du die Aufgabe löschen möchtest." }
      });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/${taskId}`,
      {
        method: "DELETE",
        includeSameOrigin: true,
        authRedirectPath
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        deleteTask: { error: "Die Aufgabe konnte nicht gelöscht werden." }
      });
    }

    return await success("deleteTask", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "Aufgabe gelöscht.");
  },

  reorderTask: async ({ fetch, cookies, params, request, url }) => {
    const authRedirectPath = actionAuthRedirectPath(url);
    const formData = await request.formData();
    const taskId = asText(formData.get("task_id"));
    const beforeId = asText(formData.get("before_id"));
    const direction = asText(formData.get("direction")) === "down" ? "down" : "up";
    const editor = await readEditor(fetch, cookies, params.unitId, params.nodeId, authRedirectPath);
    const sectionId = sectionIdForEditor(editor);
    const orderedIds = editor.tasks.map((item) => item.id);
    const nextIds = beforeId ? moveIdBefore(orderedIds, taskId, beforeId) : reorderIds(orderedIds, taskId, direction);

    if (nextIds.join(",") === orderedIds.join(",")) {
      return {
        reorderTask: {
          ok: true,
          message: "",
          editor,
          task_id: taskId
        }
      };
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/reorder`,
      {
        method: "POST",
        includeSameOrigin: true,
        authRedirectPath,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ task_ids: nextIds })
      }
    );

    if (!response.ok) {
      return fail(response.status, {
        reorderTask: { error: "Die Aufgaben konnten nicht neu geordnet werden." }
      });
    }

    return await success("reorderTask", fetch, cookies, params.unitId, params.nodeId, authRedirectPath, "", {
      task_id: taskId
    });
  }
};
