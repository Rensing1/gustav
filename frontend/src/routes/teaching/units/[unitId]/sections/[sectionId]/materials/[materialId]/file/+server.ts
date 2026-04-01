import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const GET: RequestHandler = async ({ fetch, cookies, params, url }) => {
  const disposition = url.searchParams.get("disposition") === "attachment" ? "attachment" : "inline";
  const response = await backendRequest(
    fetch,
    cookies,
    `/api/teaching/units/${encodeURIComponent(params.unitId)}/sections/${encodeURIComponent(params.sectionId)}/materials/${encodeURIComponent(params.materialId)}/download-url?disposition=${encodeURIComponent(disposition)}`,
    { method: "GET" }
  );

  if (!response.ok) {
    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "cache-control": "private, no-store",
        "content-type": response.headers.get("content-type") || "application/json"
      }
    });
  }

  const payload = (await response.json().catch(() => null)) as { url?: string } | null;
  if (!payload?.url) {
    return new Response(JSON.stringify({ error: "download_unavailable" }), {
      status: 502,
      headers: {
        "cache-control": "private, no-store",
        "content-type": "application/json"
      }
    });
  }

  return Response.redirect(payload.url, 302);
};
