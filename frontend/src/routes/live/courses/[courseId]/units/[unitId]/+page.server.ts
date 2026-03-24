import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { LiveDetailSheetView, LiveUnitMatrixView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "live");

  const matrix = await requireBackendJson<LiveUnitMatrixView>(
    fetch,
    cookies,
    `/api/live/views/courses/${params.courseId}/units/${params.unitId}/matrix`
  );

  const studentSub = url.searchParams.get("student_sub");
  const taskId = url.searchParams.get("task_id");
  let detail: LiveDetailSheetView | null = null;

  if (studentSub && taskId) {
    const query = new URLSearchParams({ student_sub: studentSub, task_id: taskId });
    detail = await requireBackendJson<LiveDetailSheetView>(
      fetch,
      cookies,
      `/api/live/views/courses/${params.courseId}/units/${params.unitId}/detail-sheet?${query.toString()}`
    );
  }

  return {
    matrix,
    detail,
    studentSub,
    taskId
  };
};
