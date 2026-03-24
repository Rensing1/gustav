import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { BackendRequestError, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { LearningCoursePageData, LearningCourseUnit } from "$lib/types/learning";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  try {
    const [bootstrap, units] = await Promise.all([
      requireSpaceBootstrap(fetch, cookies, currentPath(url), "learning"),
      requireBackendJson<LearningCourseUnit[]>(
        fetch,
        cookies,
        `/api/learning/courses/${encodeURIComponent(params.courseId)}/units`
      )
    ]);

    return {
      user: bootstrap.user,
      courseId: params.courseId,
      units
    } satisfies LearningCoursePageData;
  } catch (caught) {
    if (caught instanceof BackendRequestError) {
      throw error(caught.response.status, "Lernkurs konnte nicht geladen werden.");
    }
    throw error(500, "Lernkurs konnte nicht geladen werden.");
  }
};
