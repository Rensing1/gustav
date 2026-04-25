import type { PageServerLoad } from "./$types";

import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";

export const load: PageServerLoad = async ({ parent, url }) => {
  await requireParentSpaceBootstrap(parent, currentPath(url), "diagnostics");

  return {};
};
