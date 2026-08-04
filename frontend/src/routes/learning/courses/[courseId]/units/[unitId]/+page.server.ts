import { randomUUID } from "node:crypto";

import { error, fail, isRedirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { BackendRequestError, backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap, requireSpaceBootstrap } from "$lib/server/guards";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";
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

function submissionMode(task: LearningTask, file: File | null, textBody: string): "text" | "upload" | null {
  if (file && file.size > 0) {
    return "upload";
  }
  if (task.kind === "visual" || task.kind === "scratch" || task.kind === "calliope" || task.kind === "filius") {
    return null;
  }
  if (textBody.trim()) {
    return "text";
  }
  return null;
}

function requestedInitialView(url: URL, moduleId: string | null): "overview" | "content" {
  const raw = url.searchParams.get("view");
  if (raw === "overview") {
    return "overview";
  }
  if (raw === "content") {
    return "content";
  }
  return moduleId ? "content" : "overview";
}

async function loadPageData(
  fetchFn: typeof fetch,
  cookies: Parameters<PageServerLoad>[0]["cookies"],
  courseId: string,
  unitId: string,
  url: URL,
  moduleIdOverride: string | null = null,
  bootstrapOverride: SessionBootstrap | null = null
): Promise<LearningUnitPageData> {
  const authRedirectPath = currentPath(url);
  const bootstrap = bootstrapOverride ?? await requireSpaceBootstrap(fetchFn, cookies, authRedirectPath, "learning");
  const [units, home] = await Promise.all([
    requireBackendJson<LearningCourseUnit[]>(
      fetchFn,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units`,
      { authRedirectPath }
    ),
    requireBackendJson<LearnerHome>(
      fetchFn,
      cookies,
      "/api/learning/views/learner-home",
      { authRedirectPath }
    )
  ]);
  const selectedUnit = units.find((row) => row.unit.id === unitId) || null;
  if (!selectedUnit) {
    throw error(404, "Lerneinheit nicht gefunden.");
  }
  const courseTitle =
    home.courses.find((course) => course.id === courseId)?.title ?? "Kursraum";

  const legacyHistoryTaskId = url.searchParams.get("history");
  const rawRequestedTaskId = url.searchParams.get("task") ?? legacyHistoryTaskId;
  const moduleId = moduleIdOverride ?? url.searchParams.get("module");
  const initialView = requestedInitialView(url, moduleId);

  let sections: LearningSection[] = [];
  let graph: LearningUnitGraph | null = null;
  let activeModule: LearningModuleContent | null = null;

  if (selectedUnit.unit.unit_type === "modular") {
    graph = await requireBackendJson<LearningUnitGraph>(
      fetchFn,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/graph`,
      { authRedirectPath }
    );
    if (moduleId && initialView === "content") {
      try {
        activeModule = await requireBackendJson<LearningModuleContent>(
          fetchFn,
          cookies,
          `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/${encodeURIComponent(moduleId)}?include=materials,tasks`,
          { authRedirectPath }
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
      `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/sections?include=materials,tasks&limit=100&offset=0`,
      { authRedirectPath }
    );
  }

  const accessibleTasks = selectedUnit.unit.unit_type === "modular"
    ? activeModule?.tasks ?? []
    : sections.flatMap((section) => section.tasks);
  const requestedTaskId = rawRequestedTaskId && accessibleTasks.some((task) => task.id === rawRequestedTaskId)
    ? rawRequestedTaskId
    : null;
  const initialPanel = requestedTaskId && (url.searchParams.get("panel") === "result" || legacyHistoryTaskId)
    ? "result"
    : null;
  const historyTaskId = legacyHistoryTaskId ?? (initialPanel === "result" ? requestedTaskId : null);

  let history: LearningSubmission[] = [];
  if (historyTaskId) {
    try {
      history = await requireBackendJson<LearningSubmission[]>(
        fetchFn,
        cookies,
        `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(historyTaskId)}/submissions?limit=10&offset=0`,
        { authRedirectPath }
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
    initialView,
    requestedTaskId,
    initialPanel,
    historyTaskId,
    history,
    submittedTaskId: url.searchParams.get("submitted"),
    message: url.searchParams.get("message"),
    submissionMode:
      url.searchParams.get("submission_mode") === "upload"
        ? "upload"
        : url.searchParams.get("submission_mode") === "text"
          ? "text"
          : null
  };
}

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  try {
    const bootstrap = await requireParentSpaceBootstrap(parent, currentPath(url), "learning");
    const pageData = await loadPageData(fetch, cookies, params.courseId, params.unitId, url, null, bootstrap);
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
    const submissionIntent = form.get("submission_intent") === "feedback" ? "feedback" : "submit";
    const fileEntry = form.get("upload_file");
    const uploadFile = fileEntry instanceof File && fileEntry.size > 0 ? fileEntry : null;

    let pageData: LearningUnitPageData;
    try {
      pageData = await loadPageData(fetch, cookies, params.courseId, params.unitId, url, moduleId);
    } catch (caught) {
      if (isRedirect(caught)) {
        throw caught;
      }
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

    if (submissionIntent === "submit") {
      const response = await backendRequest(
        fetch,
        cookies,
        `/api/learning/courses/${encodeURIComponent(params.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions/finalize`,
        {
          method: "POST",
          authRedirectPath: currentPath(url),
          includeSameOrigin: true,
          headers: {
            "content-type": "application/json",
            "idempotency-key": randomUUID()
          },
          body: JSON.stringify({})
        }
      );

      if (!response.ok) {
        const backendError = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
        return fail(response.status, {
          message: backendError.detail || backendError.error || "Die finale Abgabe ist fehlgeschlagen.",
          taskId
        });
      }

      const submission = (await response.json().catch(() => null)) as Record<string, unknown> | null;
      return {
        finalizedTaskId: taskId,
        finalizedSubmission: submission,
        message: "submitted"
      };
    }

    const mode = submissionMode(task, uploadFile, textBody);
    if (!mode) {
      return fail(400, {
        message: "Bitte gib Text ein oder waehle eine passende Datei aus.",
        taskId
      });
    }

    if (mode === "upload") {
      return fail(400, {
        message: "Datei-Uploads benötigen aktiviertes JavaScript.",
        taskId
      });
    }

    const response = await backendRequest(
      fetch,
      cookies,
      `/api/learning/courses/${encodeURIComponent(params.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`,
      {
        method: "POST",
        authRedirectPath: currentPath(url),
        includeSameOrigin: true,
        headers: {
          "content-type": "application/json",
          "idempotency-key": randomUUID()
        },
        body: JSON.stringify({ intent: submissionIntent, kind: "text", text_body: textBody.trim() })
      }
    );

    if (!response.ok) {
      const backendError = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
      return fail(response.status, {
        message: backendError.detail || backendError.error || "Die Abgabe ist fehlgeschlagen.",
        taskId
      });
    }

    const submission = (await response.json().catch(() => null)) as { id?: string } | null;

    return {
      feedbackRequestedTaskId: taskId,
      feedbackSubmissionId: submission?.id ?? null,
      historyTaskId: taskId,
      message: "feedback_pending",
      pendingIntent: "feedback",
      submissionMode: mode
    };
  }
};
