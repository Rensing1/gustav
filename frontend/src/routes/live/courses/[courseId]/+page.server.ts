import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseContextView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "live");

  const course = await requireBackendJson<TeacherCourseContextView>(
    fetch,
    cookies,
    `/api/teaching/views/courses/${params.courseId}/context`
  );

  return {
    course
  };
};
