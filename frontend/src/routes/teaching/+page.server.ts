import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const home = await requireBackendJson<TeacherHome>(
    fetch,
    cookies,
    "/api/teaching/views/teacher-home"
  );

  return {
    home
  };
};
