import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  await requireParentSpaceBootstrap(parent, currentPath(url), "teaching");

  const home = await requireBackendJson<TeacherHome>(
    fetch,
    cookies,
    "/api/teaching/views/teacher-home"
  );

  return {
    home
  };
};
