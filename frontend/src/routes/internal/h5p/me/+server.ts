import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const GET: RequestHandler = async ({ fetch, cookies }) => {
  const response = await backendRequest(fetch, cookies, "/api/me", { method: "GET" });
  const bodyText = await response.text();

  return new Response(bodyText, {
    status: response.status,
    headers: {
      "cache-control": "private, no-store",
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
};
