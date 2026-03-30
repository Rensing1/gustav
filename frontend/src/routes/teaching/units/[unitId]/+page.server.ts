import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherUnitWorkspaceView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

function workspaceHref(unitId: string): string {
  return `/api/teaching/views/units/${encodeURIComponent(unitId)}/workspace`;
}

function nextPageHref(unitId: string, url: URL, next: Record<string, string | null>): string {
  const params = new URLSearchParams(url.searchParams);
  for (const [key, value] of Object.entries(next)) {
    if (!value) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }
  const query = params.toString();
  return query ? `/teaching/units/${unitId}?${query}` : `/teaching/units/${unitId}`;
}

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const apiUrl = new URL(workspaceHref(params.unitId), "http://internal");
  const paramMap: Record<string, string> = {
    section: "section_id",
    phase: "phase_id",
    module: "module_id",
    edgeFrom: "edge_from_module_id",
    edgeTo: "edge_to_module_id"
  };
  for (const [searchKey, apiKey] of Object.entries(paramMap)) {
    const value = url.searchParams.get(searchKey);
    if (value) {
      apiUrl.searchParams.set(apiKey, value);
    }
  }

  const workspace = await requireBackendJson<TeacherUnitWorkspaceView>(
    fetch,
    cookies,
    `${apiUrl.pathname}${apiUrl.search}`
  );

  const breadcrumbs: BreadcrumbItem[] = [{ label: "Lerneinheiten", href: "/teaching/units" }];

  return {
    breadcrumbs,
    hidePageHeading: true,
    pageTitle: workspace.unit.title,
    showEditDialog: url.searchParams.get("edit") == "1",
    showCreateSectionDialog: url.searchParams.get("create-section") == "1",
    showCreatePhaseDialog: url.searchParams.get("create-phase") == "1",
    showCreateModuleDialog: url.searchParams.get("create-module") == "1",
    workspace
  };
};

export const actions: Actions = {
  saveUnit: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();
    const summary = String(formData.get("summary") ?? "").trim();

    if (!title) {
      return fail(400, {
        saveUnit: {
          error: "Bitte gib einen Titel für die Lerneinheit ein.",
          values: { title, summary }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}`, {
      method: "PATCH",
      body: JSON.stringify({ title, summary: summary || null }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        saveUnit: {
          error: "Die Lerneinheit konnte nicht gespeichert werden.",
          values: { title, summary }
        }
      });
    }

    throw redirect(303, `/teaching/units/${params.unitId}`);
  },

  deleteUnit: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const confirmation = String(formData.get("confirmation") ?? "").trim();
    const expectedTitle = String(formData.get("expected_title") ?? "").trim();

    if (confirmation != expectedTitle) {
      return fail(400, { deleteUnit: { error: "Bitte gib den Titel exakt zur Bestätigung ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deleteUnit: { error: "Die Lerneinheit konnte nicht gelöscht werden." } });
    }

    throw redirect(303, "/teaching/units");
  },

  saveSection: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();
    const title = String(formData.get("title") ?? "").trim();

    if (!sectionId || !title) {
      return fail(400, { saveSection: { error: "Bitte gib einen Abschnittstitel ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { saveSection: { error: "Der Abschnitt konnte nicht gespeichert werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { section: sectionId }));
  },

  createSection: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();

    if (!title) {
      return fail(400, { createSection: { error: "Bitte gib einen Abschnittstitel ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections`, {
      method: "POST",
      body: JSON.stringify({ title }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createSection: { error: "Der Abschnitt konnte nicht angelegt werden." } });
    }

    const created = await response.json();
    throw redirect(303, nextPageHref(params.unitId, url, { section: created.id, "create-section": null }));
  },

  deleteSection: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const sectionId = String(formData.get("section_id") ?? "").trim();

    if (!sectionId) {
      return fail(400, { deleteSection: { error: "Es wurde kein Abschnitt ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/sections/${sectionId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deleteSection: { error: "Der Abschnitt konnte nicht entfernt werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { section: null }));
  },

  savePhase: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const phaseId = String(formData.get("phase_id") ?? "").trim();
    const title = String(formData.get("title") ?? "").trim();

    if (!phaseId || !title) {
      return fail(400, { savePhase: { error: "Bitte gib einen Phasentitel ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/phases/${phaseId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { savePhase: { error: "Die Phase konnte nicht gespeichert werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { phase: phaseId }));
  },

  createPhase: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();

    if (!title) {
      return fail(400, { createPhase: { error: "Bitte gib einen Phasentitel ein." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/phases`, {
      method: "POST",
      body: JSON.stringify({ title }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createPhase: { error: "Die Phase konnte nicht angelegt werden." } });
    }

    const created = await response.json();
    throw redirect(303, nextPageHref(params.unitId, url, { phase: created.id, "create-phase": null }));
  },

  deletePhase: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const phaseId = String(formData.get("phase_id") ?? "").trim();

    if (!phaseId) {
      return fail(400, { deletePhase: { error: "Es wurde keine Phase ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/phases/${phaseId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deletePhase: { error: "Die Phase konnte nicht entfernt werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { phase: null }));
  },

  saveModule: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const moduleId = String(formData.get("module_id") ?? "").trim();
    const title = String(formData.get("title") ?? "").trim();
    const requiredPrereqCountRaw = String(formData.get("required_prereq_count") ?? "").trim();
    const requiredPrereqCount = Number.parseInt(requiredPrereqCountRaw, 10);

    if (!moduleId || !title || !Number.isInteger(requiredPrereqCount) || requiredPrereqCount < 0) {
      return fail(400, { saveModule: { error: "Bitte prüfe Titel und Freischaltung des Moduls." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/modules/${moduleId}`, {
      method: "PATCH",
      body: JSON.stringify({ title, required_prereq_count: requiredPrereqCount }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { saveModule: { error: "Das Modul konnte nicht gespeichert werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { module: moduleId }));
  },

  createModule: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();
    const phaseId = String(formData.get("phase_id") ?? "").trim();

    if (!title || !phaseId) {
      return fail(400, { createModule: { error: "Bitte gib Titel und Phase für das Modul an." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/modules`, {
      method: "POST",
      body: JSON.stringify({ title, phase_id: phaseId }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createModule: { error: "Das Modul konnte nicht angelegt werden." } });
    }

    const created = await response.json();
    throw redirect(303, nextPageHref(params.unitId, url, { module: created.id, "create-module": null }));
  },

  deleteModule: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const moduleId = String(formData.get("module_id") ?? "").trim();

    if (!moduleId) {
      return fail(400, { deleteModule: { error: "Es wurde kein Modul ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/modules/${moduleId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { deleteModule: { error: "Das Modul konnte nicht entfernt werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { module: null, edgeFrom: null, edgeTo: null }));
  },

  createEdge: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const fromModuleId = String(formData.get("from_module_id") ?? "").trim();
    const toModuleId = String(formData.get("to_module_id") ?? "").trim();

    if (!fromModuleId || !toModuleId) {
      return fail(400, { createEdge: { error: "Bitte wähle Start- und Zielmodul." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/units/${params.unitId}/modules/edges`, {
      method: "POST",
      body: JSON.stringify({ from_module_id: fromModuleId, to_module_id: toModuleId }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, { createEdge: { error: "Die Kante konnte nicht angelegt werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { edgeFrom: fromModuleId, edgeTo: toModuleId, module: toModuleId }));
  },

  deleteEdge: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const fromModuleId = String(formData.get("from_module_id") ?? "").trim();
    const toModuleId = String(formData.get("to_module_id") ?? "").trim();

    if (!fromModuleId || !toModuleId) {
      return fail(400, { deleteEdge: { error: "Es wurde keine Kante ausgewählt." } });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/units/${params.unitId}/modules/${fromModuleId}/edges/${toModuleId}`,
      { method: "DELETE", includeSameOrigin: true }
    );

    if (!response.ok) {
      return fail(response.status, { deleteEdge: { error: "Die Kante konnte nicht gelöscht werden." } });
    }

    throw redirect(303, nextPageHref(params.unitId, url, { edgeTo: null }));
  }
};
