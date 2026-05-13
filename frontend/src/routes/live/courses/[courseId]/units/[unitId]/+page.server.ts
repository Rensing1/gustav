import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LiveDetailSheetView, LiveUnitMatrixView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "live");

  const matrix = await requireBackendJson<LiveUnitMatrixView>(
    fetch,
    cookies,
    `/api/live/views/courses/${params.courseId}/units/${params.unitId}/matrix`,
    { authRedirectPath }
  );

  const studentSub = url.searchParams.get("student_sub");
  const taskId = url.searchParams.get("task_id");
  let detail: LiveDetailSheetView | null = null;

  if (studentSub && taskId) {
    const query = new URLSearchParams({ student_sub: studentSub, task_id: taskId });
    detail = await requireBackendJson<LiveDetailSheetView>(
      fetch,
      cookies,
      `/api/live/views/courses/${params.courseId}/units/${params.unitId}/detail-sheet?${query.toString()}`,
      { authRedirectPath }
    );
  }

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Kurse",
      href: "/live"
    },
    {
      label: matrix.course.title,
      href: matrix.course.href
    },
    {
      label: matrix.unit.title
    }
  ];

  return {
    breadcrumbs,
    detail,
    matrix,
    pageCopy: "Matrix und Detail-Sheet bleiben in derselben Unterrichtsansicht gekoppelt.",
    pageTitle: matrix.unit.title,
    studentSub,
    taskId
  };
};
