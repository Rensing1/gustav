import type { PageServerLoad } from "./$types";

import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  const bootstrap = await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  return {
    bootstrap
  };
};
