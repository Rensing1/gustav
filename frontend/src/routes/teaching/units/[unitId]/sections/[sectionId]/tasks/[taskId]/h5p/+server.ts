import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const PATCH: RequestHandler = async ({ fetch, cookies, params, request }) => {
  const body = await request.text();
  const response = await backendRequest(
    fetch,
    cookies,
    `/api/teaching/units/${encodeURIComponent(params.unitId)}/sections/${encodeURIComponent(params.sectionId)}/tasks/${encodeURIComponent(params.taskId)}`,
    {
      method: "PATCH",
      includeSameOrigin: true,
      headers: { "content-type": "application/json" },
      body
    }
  );

  return new Response(await response.text(), {
    status: response.status,
    headers: {
      "cache-control": "private, no-store",
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
};
