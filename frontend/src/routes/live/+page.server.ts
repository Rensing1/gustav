import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";

type LiveCourseListItem = {
  id: string;
  title: string;
};

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "live");

  const courses = await requireBackendJson<LiveCourseListItem[]>(
    fetch,
    cookies,
    "/api/teaching/courses?limit=25&offset=0"
  );

  return {
    courses
  };
};
