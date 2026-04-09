import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { LiveCourseUnitsView, LiveUnitDashboardView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

type LiveCourseListItem = {
  id: string;
  title: string;
};

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "live");

  const courses = await requireBackendJson<LiveCourseListItem[]>(
    fetch,
    cookies,
    "/api/teaching/courses?limit=25&offset=0"
  );

  const selectedCourseId = url.searchParams.get("course_id");
  const selectedUnitId = url.searchParams.get("unit_id");
  const selectedStudentSub = url.searchParams.get("student_sub");
  const selectedTaskId = url.searchParams.get("task_id");

  let courseUnits: LiveCourseUnitsView | null = null;
  let dashboard: LiveUnitDashboardView | null = null;

  if (selectedCourseId) {
    courseUnits = await requireBackendJson<LiveCourseUnitsView>(
      fetch,
      cookies,
      `/api/live/views/courses/${selectedCourseId}/units`
    );
  }

  if (selectedCourseId && selectedUnitId) {
    const query = new URLSearchParams();
    if (selectedStudentSub) {
      query.set("student_sub", selectedStudentSub);
    }
    if (selectedTaskId) {
      query.set("task_id", selectedTaskId);
    }
    dashboard = await requireBackendJson<LiveUnitDashboardView>(
      fetch,
      cookies,
      `/api/live/views/courses/${selectedCourseId}/units/${selectedUnitId}/dashboard${query.size ? `?${query.toString()}` : ""}`
    );

    const defaultTaskId = dashboard.selected_student_panel?.selected_task_id;
    if (selectedStudentSub && !selectedTaskId && defaultTaskId) {
      const nextQuery = new URLSearchParams();
      nextQuery.set("course_id", selectedCourseId);
      nextQuery.set("unit_id", selectedUnitId);
      nextQuery.set("student_sub", selectedStudentSub);
      nextQuery.set("task_id", defaultTaskId);
      throw redirect(302, `/live?${nextQuery.toString()}`);
    }
  }

  return {
    breadcrumbs: [{ label: "Live" }] satisfies BreadcrumbItem[],
    courseUnits,
    courses,
    dashboard,
    selectedCourseId,
    selectedStudentSub,
    selectedTaskId,
    selectedUnitId,
    wideWorkspaceShell: true
  };
};
