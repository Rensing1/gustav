import { json } from "@sveltejs/kit";

import { proxyBackendWrite } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ fetch, cookies, params, request }) => {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ error: "bad_request", detail: "invalid_json" }, { status: 400 });
  }

  return proxyBackendWrite({
    fetchFn: fetch,
    cookies,
    path: `/api/teaching/units/${params.unitId}/sections/reorder`,
    method: "POST",
    body
  });
};
