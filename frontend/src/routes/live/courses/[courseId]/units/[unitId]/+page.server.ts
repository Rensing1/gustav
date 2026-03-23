import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { LiveDetailSheetView, LiveUnitMatrixView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  const matrix = await readTypedJsonOrNull<LiveUnitMatrixView>(
    fetch,
    cookies,
    `/api/live/views/courses/${params.courseId}/units/${params.unitId}/matrix`
  );

  const studentSub = url.searchParams.get("student_sub");
  const taskId = url.searchParams.get("task_id");
  let detail: LiveDetailSheetView | null = null;

  if (studentSub && taskId) {
    const query = new URLSearchParams({ student_sub: studentSub, task_id: taskId });
    detail = await readTypedJsonOrNull<LiveDetailSheetView>(
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
