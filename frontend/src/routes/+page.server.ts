import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { currentPath, requireSessionBootstrap } from "$lib/server/guards";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  const bootstrap = await requireSessionBootstrap(fetch, cookies, currentPath(url));
  throw redirect(303, bootstrap.start_target);
};
