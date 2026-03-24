import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { LearnerHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "learning");

  const home = await requireBackendJson<LearnerHome>(
    fetch,
    cookies,
    "/api/learning/views/learner-home"
  );

  return {
    home
  };
};
