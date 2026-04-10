import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const GET: RequestHandler = async ({ fetch, cookies, url }) => {
  const courseId = url.searchParams.get("course_id");
  const contentId = url.searchParams.get("content_id");

  if (!courseId || !contentId) {
    return new Response(JSON.stringify({ error: "invalid_request" }), {
      status: 400,
      headers: {
        "cache-control": "private, no-store",
        "content-type": "application/json"
      }
    });
  }

  const response = await backendRequest(
    fetch,
    cookies,
    `/api/learning/courses/${encodeURIComponent(courseId)}/h5p/contents/${encodeURIComponent(contentId)}/access`,
    { method: "GET" }
  );
  const bodyText = await response.text();

  return new Response(bodyText, {
    status: response.status,
    headers: {
      "cache-control": "private, no-store",
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
};
