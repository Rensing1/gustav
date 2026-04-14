import { proxyBackendRead } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

function deltaPath(courseId: string, unitId: string, searchParams: URLSearchParams): string {
  const apiUrl = new URL(
    `/api/teaching/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/submissions/delta`,
    "http://internal"
  );
  const updatedSince = searchParams.get("updated_since");
  if (updatedSince) {
    apiUrl.searchParams.set("updated_since", updatedSince);
  }
  return `${apiUrl.pathname}${apiUrl.search}`;
}

export const GET: RequestHandler = async ({ fetch, cookies, params, url }) => {
  return await proxyBackendRead({
    fetchFn: fetch,
    cookies,
    path: deltaPath(params.courseId, params.unitId, url.searchParams)
  });
};
