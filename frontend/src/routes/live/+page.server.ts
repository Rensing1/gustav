import type { PageServerLoad } from "./$types";

import { readJsonOrNull } from "$lib/server/api";

type LiveCourseListItem = {
  id: string;
  title: string;
};

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const courses =
    (await readJsonOrNull(fetch, cookies, "/api/teaching/courses?limit=25&offset=0")) as
      | LiveCourseListItem[]
      | null;

  return {
    courses: courses ?? []
  };
};
