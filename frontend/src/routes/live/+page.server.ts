import { env } from "$env/dynamic/private";
import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LiveCourseUnitsView, LiveDetailSheetView, LiveDialogTranscript, LiveSummaryPayload } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";
import { buildLivePageHref, normalizeLiveSelection } from "./page-state";

type LiveCourseListItem = {
  id: string;
  title: string;
};

function loadLivePollIntervalSeconds(): number {
  const raw = String(env.GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS ?? "3").trim();
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    return 3;
  }
  return Math.min(60, Math.max(1, parsed));
}

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "live");

  const courses = await requireBackendJson<LiveCourseListItem[]>(
    fetch,
    cookies,
    "/api/teaching/courses?limit=25&offset=0",
    { authRedirectPath }
  );

  const selectedCourseId = url.searchParams.get("course_id");
  const selectedUnitId = url.searchParams.get("unit_id");
  const selectedStudentSub = url.searchParams.get("student_sub");
  const selectedTaskId = url.searchParams.get("task_id");

  let courseUnits: LiveCourseUnitsView | null = null;
  let summary: LiveSummaryPayload | null = null;
  let detail: LiveDetailSheetView | null = null;

  if (selectedCourseId) {
    courseUnits = await requireBackendJson<LiveCourseUnitsView>(
      fetch,
      cookies,
      `/api/live/views/courses/${selectedCourseId}/units`,
      { authRedirectPath }
    );
  }

  if (selectedCourseId && selectedUnitId) {
    summary = await requireBackendJson<LiveSummaryPayload>(
      fetch,
      cookies,
      `/api/teaching/courses/${selectedCourseId}/units/${selectedUnitId}/submissions/summary`,
      { authRedirectPath }
    );

    const normalizedSelection = normalizeLiveSelection(summary, {
      courseId: selectedCourseId,
      unitId: selectedUnitId,
      studentSub: selectedStudentSub,
      taskId: selectedTaskId
    });
    const canonicalHref = buildLivePageHref(normalizedSelection);
    const requestedHref = buildLivePageHref({
      courseId: selectedCourseId,
      unitId: selectedUnitId,
      studentSub: selectedStudentSub,
      taskId: selectedTaskId
    });
    if (canonicalHref !== requestedHref) {
      throw redirect(302, canonicalHref);
    }

    if (normalizedSelection.studentSub && normalizedSelection.taskId) {
      const query = new URLSearchParams({
        student_sub: normalizedSelection.studentSub,
        task_id: normalizedSelection.taskId
      });
      detail = await requireBackendJson<LiveDetailSheetView>(
        fetch,
        cookies,
        `/api/live/views/courses/${selectedCourseId}/units/${selectedUnitId}/detail-sheet?${query.toString()}`,
        { authRedirectPath }
      );
      if (detail.submission?.kind === "dialog") {
        const transcript = await requireBackendJson<LiveDialogTranscript>(
          fetch,
          cookies,
          `/api/teaching/courses/${encodeURIComponent(selectedCourseId)}/units/${encodeURIComponent(selectedUnitId)}/tasks/${encodeURIComponent(normalizedSelection.taskId)}/students/${encodeURIComponent(normalizedSelection.studentSub)}/submissions/${encodeURIComponent(detail.submission.id)}/dialog`,
          { authRedirectPath }
        );
        detail = {
          ...detail,
          submission: { ...detail.submission, dialog: transcript }
        };
      }
    }
  }

  return {
    breadcrumbs: [{ label: "Live" }] satisfies BreadcrumbItem[],
    courseUnits,
    courses,
    detail,
    liveCursorSeed: summary?.cursor ?? null,
    livePollIntervalSeconds: loadLivePollIntervalSeconds(),
    liveWideWorkspaceShell: true,
    selectedCourseId,
    selectedStudentSub,
    selectedTaskId,
    selectedUnitId,
    summary,
    wideWorkspaceShell: true
  };
};
