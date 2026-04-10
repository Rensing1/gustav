import { json } from "@sveltejs/kit";

import { proxyBackendWrite } from "$lib/server/bff-proxy";
import type { RequestHandler } from "./$types";

type ModuleReorderPayload = {
  phase_id?: string;
  module_ids?: string[];
};

export const POST: RequestHandler = async ({ fetch, cookies, params, request }) => {
  let body: ModuleReorderPayload;
  try {
    body = (await request.json()) as ModuleReorderPayload;
  } catch {
    return json({ error: "bad_request", detail: "invalid_json" }, { status: 400 });
  }

  const phaseId = String(body.phase_id ?? "").trim();
  if (!phaseId) {
    return json({ error: "bad_request", detail: "invalid_phase_id" }, { status: 400 });
  }

  return proxyBackendWrite({
    fetchFn: fetch,
    cookies,
    path: `/api/teaching/units/${params.unitId}/phases/${phaseId}/modules/reorder`,
    method: "POST",
    body: { module_ids: body.module_ids ?? [] }
  });
};
