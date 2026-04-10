import type { PageServerLoad } from "./$types";

import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "diagnostics");

  return {};
};
