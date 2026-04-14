import { proxyBackendRead } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

function detailSheetPath(courseId: string, unitId: string, searchParams: URLSearchParams): string {
  const apiUrl = new URL(
    `/api/live/views/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/detail-sheet`,
    "http://internal"
  );
  const studentSub = searchParams.get("student_sub");
  const taskId = searchParams.get("task_id");
  if (studentSub) {
    apiUrl.searchParams.set("student_sub", studentSub);
  }
  if (taskId) {
    apiUrl.searchParams.set("task_id", taskId);
  }
  return `${apiUrl.pathname}${apiUrl.search}`;
}

export const GET: RequestHandler = async ({ fetch, cookies, params, url }) => {
  return await proxyBackendRead({
    fetchFn: fetch,
    cookies,
    path: detailSheetPath(params.courseId, params.unitId, url.searchParams)
  });
};
