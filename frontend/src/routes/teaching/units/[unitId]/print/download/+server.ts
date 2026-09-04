import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const POST: RequestHandler = async ({ fetch, cookies, params, request }) => {
  const form = await request.formData();
  const materialIds = form.getAll("material_id").map(String);
  const taskIds = form.getAll("task_id").map(String);
  const response = await backendRequest(
    fetch,
    cookies,
    `/api/teaching/units/${encodeURIComponent(params.unitId)}/printable-pdf`,
    {
      method: "POST",
      body: JSON.stringify({ material_ids: materialIds, task_ids: taskIds }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    }
  );
  const contentType = response.headers.get("content-type") || "application/json";
  const disposition = response.headers.get("content-disposition");
  const headers = new Headers({
    "cache-control": "private, no-store",
    "content-type": contentType,
    "x-content-type-options": "nosniff"
  });
  if (disposition && response.ok && contentType.startsWith("application/pdf")) {
    headers.set("content-disposition", disposition);
  }
  return new Response(await response.arrayBuffer(), { status: response.status, headers });
};
