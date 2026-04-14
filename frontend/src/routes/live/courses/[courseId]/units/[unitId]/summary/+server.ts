import { proxyBackendRead } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

export const GET: RequestHandler = async ({ fetch, cookies, params }) => {
  return await proxyBackendRead({
    fetchFn: fetch,
    cookies,
    path: `/api/teaching/courses/${encodeURIComponent(params.courseId)}/units/${encodeURIComponent(params.unitId)}/submissions/summary`
  });
};
