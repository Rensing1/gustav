import { error, json, type RequestHandler } from "@sveltejs/kit";

import { BackendRequestError, requireBackendJson } from "$lib/server/api";
import { currentPath } from "$lib/server/guards";
import type { LearningModuleContent } from "$lib/types/learning";

export const GET: RequestHandler = async ({ fetch, cookies, params, url }) => {
  const include = url.searchParams.get("include")?.trim() || "materials,tasks";
  const courseId = params.courseId ?? "";
  const unitId = params.unitId ?? "";
  const moduleId = params.moduleId ?? "";

  try {
    const payload = await requireBackendJson<LearningModuleContent>(
      fetch,
      cookies,
      `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/${encodeURIComponent(moduleId)}?include=${encodeURIComponent(include)}`,
      { authRedirectPath: currentPath(url) }
    );

    return json(payload, {
      headers: {
        "cache-control": "no-store"
      }
    });
  } catch (caught) {
    if (caught instanceof BackendRequestError) {
      throw error(caught.response.status, "Modul konnte nicht geladen werden.");
    }
    throw caught;
  }
};
