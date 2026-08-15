import type { PageServerLoad } from "./$types";

import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";

export const load: PageServerLoad = async ({ parent, url }) => {
  const bootstrap = await requireParentSpaceBootstrap(parent, currentPath(url), "teaching");

  return {
    bootstrap,
    workspaceLayout: "wide"
  };
};
