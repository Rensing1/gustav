import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { BackendRequestError, requireBackendJson } from "$lib/server/api";
import type { LearningCoursePageData, LearningCourseUnit } from "$lib/types/learning";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";

export const load: PageServerLoad = async ({ fetch, cookies, params }) => {
  try {
    const [bootstrap, units] = await Promise.all([
      requireBackendJson<SessionBootstrap>(fetch, cookies, "/api/app/session-bootstrap"),
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
