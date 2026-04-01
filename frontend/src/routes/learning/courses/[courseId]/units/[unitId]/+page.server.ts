import { randomUUID } from "node:crypto";

import { error, fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { BackendRequestError, backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { LearnerHome } from "$lib/types/home";
import type {
  LearningCourseUnit,
  LearningModuleContent,
  LearningSection,
  LearningSubmission,
  LearningTask,
  LearningUnitGraph,
  LearningUnitPageData
} from "$lib/types/learning";
import type { BreadcrumbItem } from "$lib/types/navigation";

function historyHref(url: URL, taskId: string, moduleId: string | null): string {
  const next = new URL(url);
  next.searchParams.set("history", taskId);
  if (moduleId) {
    next.searchParams.set("module", moduleId);
  }
  return `${next.pathname}?${next.searchParams.toString()}`;
}

function canonicalUploadMimeType(task: LearningTask, file: File): string {
  if (task.kind === "scratch") {
    return "application/x.scratch.sb3";
  }
  if (task.kind === "calliope") {
    return "application/x.makecode.hex";
  }
  const fileType = String(file.type || "").trim().toLowerCase();
  if (fileType) {
    return fileType;
  }
  return task.kind === "visual" ? "image/png" : "application/pdf";
}

function submissionMode(task: LearningTask, file: File | null, textBody: string): "text" | "upload" | null {
  if (file && file.size > 0) {
    return "upload";
  }
  if (task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope") {
    return null;
  }
  if (textBody.trim()) {
    return "text";
  }
  return null;
}

async function loadPageData(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  courseId: string,
  unitId: string,
  url: URL
): Promise<LearningUnitPageData> {
  const [bootstrap, units, home] = await Promise.all([
    requireSpaceBootstrap(fetchFn, cookies, currentPath(url), "learning"),
    requireBackendJson<LearningCourseUnit[]>(
      fetchFn,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units`
    ),
    requireBackendJson<LearnerHome>(
      fetchFn,
      cookies,
      "/api/learning/views/learner-home"
    )
  ]);
  const selectedUnit = units.find((row) => row.unit.id === unitId) || null;
  if (!selectedUnit) {
    throw error(404, "Lerneinheit nicht gefunden.");
  }
  const courseTitle =
    home.courses.find((course) => course.id === courseId)?.title ?? "Kursraum";

  const historyTaskId = url.searchParams.get("history");
  const moduleId = url.searchParams.get("module");

  let sections: LearningSection[] = [];
  let graph: LearningUnitGraph | null = null;
  let activeModule: LearningModuleContent | null = null;

  if (selectedUnit.unit.unit_type === "modular") {
    graph = await requireBackendJson<LearningUnitGraph>(
      fetchFn,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/graph`
    );
    if (moduleId) {
      try {
        activeModule = await requireBackendJson<LearningModuleContent>(
          fetchFn,
          cookies,
          `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/${encodeURIComponent(moduleId)}?include=materials,tasks`
        );
      } catch (caught) {
        if (!(caught instanceof BackendRequestError) || caught.response.status !== 404) {
          throw caught;
        }
      }
    }
  } else {
    sections = await requireBackendJson<LearningSection[]>(
      fetchFn,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/sections?include=materials,tasks&limit=100&offset=0`
    );
  }

  let history: LearningSubmission[] = [];
  if (historyTaskId) {
    try {
      history = await requireBackendJson<LearningSubmission[]>(
        fetchFn,
        cookies,
        `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(historyTaskId)}/submissions?limit=10&offset=0`
      );
    } catch (caught) {
      if (!(caught instanceof BackendRequestError) || caught.response.status !== 404) {
        throw caught;
      }
    }
  }

  return {
    user: bootstrap.user,
    courseId,
    courseTitle,
    unitId,
    units,
    selectedUnit,
    sections,
    graph,
    activeModule,
    historyTaskId,
    history,
    submittedTaskId: url.searchParams.get("submitted"),
    message: url.searchParams.get("message")
  };
}

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  try {
    const pageData = await loadPageData(fetch, cookies, params.courseId, params.unitId, url);
    const breadcrumbs: BreadcrumbItem[] = [
      { label: "Lernraum", href: "/learning" },
      { label: pageData.courseTitle, href: `/learning/courses/${encodeURIComponent(params.courseId)}` },
      { label: pageData.selectedUnit?.unit.title ?? "Lerneinheit" }
    ];

    return {
      ...pageData,
      breadcrumbs,
      hidePageHeading: true,
      pageTitle: pageData.selectedUnit?.unit.title ?? "Lerneinheit"
    };
  } catch (caught) {
    if (caught instanceof BackendRequestError) {
      throw error(caught.response.status, "Lernraum konnte nicht geladen werden.");
    }
    throw caught;
  }
};

export const actions: Actions = {
  default: async ({ fetch, cookies, params, request, url }) => {
    const form = await request.formData();
    const taskId = String(form.get("task_id") || "");
    const taskKind = String(form.get("task_kind") || "native");
    const unitType = String(form.get("unit_type") || "linear");
    const moduleId = String(form.get("module_id") || "").trim() || null;
    const textBody = String(form.get("text_body") || "");
    const fileEntry = form.get("upload_file");
    const uploadFile = fileEntry instanceof File && fileEntry.size > 0 ? fileEntry : null;

    let pageData: LearningUnitPageData;
    try {
      pageData = await loadPageData(fetch, cookies, params.courseId, params.unitId, url);
    } catch {
      return fail(400, {
        message: "Die Lerneinheit konnte fuer die Abgabe nicht geladen werden.",
        taskId
      });
    }

    const tasks =
      unitType === "modular"
        ? pageData.activeModule?.tasks || []
        : pageData.sections.flatMap((section) => section.tasks);
    const task = tasks.find((candidate) => candidate.id === taskId);
    if (!task) {
      return fail(400, {
        message: "Die Aufgabe ist in diesem Lernraum nicht verfuegbar.",
        taskId
      });
    }

    const mode = submissionMode(task, uploadFile, textBody);
    if (!mode) {
      return fail(400, {
        message: "Bitte gib Text ein oder waehle eine passende Datei aus.",
        taskId
      });
    }

    let payload: Record<string, string | number> = {};
    if (mode === "text") {
      payload = { kind: "text", text_body: textBody.trim() };
    } else {
      const mimeType = canonicalUploadMimeType(task, uploadFile as File);
      const intent = await requireBackendJson<{
        storage_key: string;
        url: string;
        headers: Record<string, string>;
      }>(
        fetch,
        cookies,
        `/api/learning/courses/${encodeURIComponent(params.courseId)}/tasks/${encodeURIComponent(taskId)}/upload-intents`,
        {
          method: "POST",
          includeSameOrigin: true,
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            kind: mimeType.startsWith("image/") ? "image" : "file",
            filename: (uploadFile as File).name || "submission.bin",
            mime_type: mimeType,
            size_bytes: (uploadFile as File).size
          })
        }
      );

      const uploadUrl = intent.url.startsWith("http")
        ? intent.url
        : new URL(intent.url, "http://gustav-alpha2:8000").toString();
      const uploadResponse = await fetch(uploadUrl, {
        method: "PUT",
        headers: intent.headers,
        body: uploadFile
      });
      if (!uploadResponse.ok) {
        return fail(502, {
          message: "Die Datei konnte nicht gespeichert werden.",
          taskId
        });
      }

      const uploadResult = (await uploadResponse.json().catch(() => null)) as
        | { sha256?: string; size_bytes?: number }
        | null;
      if (!uploadResult?.sha256 || !uploadResult?.size_bytes) {
        return fail(502, {
          message: "Die Upload-Antwort ist unvollstaendig.",
          taskId
        });
      }

      payload = {
        kind: mimeType.startsWith("image/") ? "image" : "file",
        storage_key: intent.storage_key,
        mime_type: mimeType,
        size_bytes: uploadResult.size_bytes,
        sha256: uploadResult.sha256
      };
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/learning/courses/${encodeURIComponent(params.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`,
      {
        method: "POST",
        includeSameOrigin: true,
        headers: {
          "content-type": "application/json",
          "idempotency-key": randomUUID()
        },
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      const backendError = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
      return fail(response.status, {
        message: backendError.detail || backendError.error || "Die Abgabe ist fehlgeschlagen.",
        taskId
      });
    }

    const destination = new URL(url);
    destination.searchParams.set("history", taskId);
    destination.searchParams.set("submitted", taskId);
    destination.searchParams.set("message", "submitted");
    if (moduleId) {
      destination.searchParams.set("module", moduleId);
    }
    throw redirect(303, `${destination.pathname}?${destination.searchParams.toString()}`);
  }
};
