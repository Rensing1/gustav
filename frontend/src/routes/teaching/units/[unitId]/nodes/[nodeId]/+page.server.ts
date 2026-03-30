import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherUnitNodeEditorView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

function editorHref(unitId: string, nodeId: string): string {
  return `/api/teaching/views/units/${encodeURIComponent(unitId)}/nodes/${encodeURIComponent(nodeId)}/editor`;
}

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const editor = await requireBackendJson<TeacherUnitNodeEditorView>(
    fetch,
    cookies,
    editorHref(params.unitId, params.nodeId)
  );

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
    const kind = String(formData.get("kind") ?? "").trim();
    const title = String(formData.get("title") ?? "").trim();
    const requiredPrereqCountRaw = String(formData.get("required_prereq_count") ?? "").trim();

    if (!title) {
      return fail(400, { saveNode: { error: "Bitte gib einen Titel ein." } });
    }

    let path = `/api/teaching/units/${params.unitId}/sections/${params.nodeId}`;
    let payload: Record<string, unknown> = { title };

    if (kind === "module") {
      const requiredPrereqCount = Number.parseInt(requiredPrereqCountRaw, 10);
      if (!Number.isInteger(requiredPrereqCount) || requiredPrereqCount < 0) {
        return fail(400, { saveNode: { error: "Bitte gib eine gültige Freischaltung ein." } });
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
      return fail(response.status, { saveNode: { error: "Der Knoten konnte nicht gespeichert werden." } });
    }

    throw redirect(303, `/teaching/units/${params.unitId}/nodes/${params.nodeId}`);
  },

  createMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();
    const title = String(formData.get("title") ?? "").trim();
    const bodyMd = String(formData.get("body_md") ?? "").trim();

    if (!sectionId || !title || !bodyMd) {
      return fail(400, { createMaterial: { error: "Bitte gib Titel und Inhalt für das Material ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials`, {
      method: "POST",
      body: JSON.stringify({ title, body_md: bodyMd }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createMaterial: { error: "Das Material konnte nicht angelegt werden." } });
    }

    throw redirect(303, `/teaching/units/${params.unitId}/nodes/${params.nodeId}`);
  },

  deleteMaterial: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();
    const materialId = String(formData.get("material_id") ?? "").trim();

    if (!sectionId || !materialId) {
      return fail(400, { deleteMaterial: { error: "Es wurde kein Material ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}/materials/${materialId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deleteMaterial: { error: "Das Material konnte nicht gelöscht werden." } });
    }

    throw redirect(303, `/teaching/units/${params.unitId}/nodes/${params.nodeId}`);
  },

  createTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();
    const instructionMd = String(formData.get("instruction_md") ?? "").trim();

    if (!sectionId || !instructionMd) {
      return fail(400, { createTask: { error: "Bitte gib eine Aufgabenstellung ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks`, {
      method: "POST",
      body: JSON.stringify({ instruction_md: instructionMd }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createTask: { error: "Die Aufgabe konnte nicht angelegt werden." } });
    }

    throw redirect(303, `/teaching/units/${params.unitId}/nodes/${params.nodeId}`);
  },

  deleteTask: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();
    const taskId = String(formData.get("task_id") ?? "").trim();

    if (!sectionId || !taskId) {
      return fail(400, { deleteTask: { error: "Es wurde keine Aufgabe ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}/tasks/${taskId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deleteTask: { error: "Die Aufgabe konnte nicht gelöscht werden." } });
    }

    throw redirect(303, `/teaching/units/${params.unitId}/nodes/${params.nodeId}`);
  }
};
