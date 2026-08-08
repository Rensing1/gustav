import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const POST: RequestHandler = async ({ fetch, cookies, request, url }) => {
  const sessionId = url.searchParams.get("session_id");
  const itemId = url.searchParams.get("item_id");
  if (!sessionId || !itemId) {
    return Response.json({ error: "invalid_request" }, { status: 400 });
  }
  const response = await backendRequest(
    fetch,
    cookies,
    `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/attempts`,
    {
      method: "POST",
      body: await request.text(),
      includeSameOrigin: true,
      headers: { "content-type": "application/json" }
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
