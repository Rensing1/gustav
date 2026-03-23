import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { TeacherCourseContextView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params }) => {
  const course = await readTypedJsonOrNull<TeacherCourseContextView>(
    fetch,
    cookies,
    `/api/teaching/views/courses/${params.courseId}/context`
  );

  return {
    course
  };
};
