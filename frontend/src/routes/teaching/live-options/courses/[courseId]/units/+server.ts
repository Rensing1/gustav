import { proxyBackendRead } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

/**
 * Load the units available for a teacher's selected course.
 *
 * The browser calls this route with its BFF session. The server then performs
 * the authenticated backend request, keeping backend credentials out of the
 * browser and preserving the existing owner checks.
 */
export const GET: RequestHandler = async ({ fetch, cookies, params }) => {
  return await proxyBackendRead({
    fetchFn: fetch,
    cookies,
    path: `/api/live/views/courses/${encodeURIComponent(params.courseId)}/units`
  });
};
