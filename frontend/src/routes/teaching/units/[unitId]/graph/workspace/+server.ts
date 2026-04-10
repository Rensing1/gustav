import { json } from "@sveltejs/kit";

import { requireBackendJson } from "$lib/server/api";
import type { TeacherUnitWorkspaceView } from "$lib/types/home";
import type { RequestHandler } from "./$types";

const WORKSPACE_PARAM_MAP: Record<string, string> = {
  section: "section_id",
  phase: "phase_id",
  module: "module_id",
  edgeFrom: "edge_from_module_id",
  edgeTo: "edge_to_module_id"
};

function workspacePath(unitId: string, searchParams: URLSearchParams): string {
  const apiUrl = new URL(`/api/teaching/views/units/${encodeURIComponent(unitId)}/workspace`, "http://internal");
  for (const [searchKey, apiKey] of Object.entries(WORKSPACE_PARAM_MAP)) {
    const value = searchParams.get(searchKey);
    if (value) {
      apiUrl.searchParams.set(apiKey, value);
    }
  }
  return `${apiUrl.pathname}${apiUrl.search}`;
}

export const GET: RequestHandler = async ({ fetch, cookies, params, url }) => {
  const workspace = await requireBackendJson<TeacherUnitWorkspaceView>(
    fetch,
    cookies,
    workspacePath(params.unitId, url.searchParams)
  );
  return json(workspace);
};
