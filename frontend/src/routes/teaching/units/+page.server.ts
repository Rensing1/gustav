import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";

type TeachingUnitListItem = {
  id: string;
  title: string;
  summary?: string | null;
  unit_type?: string | null;
};

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const units = await requireBackendJson<TeachingUnitListItem[]>(
    fetch,
    cookies,
    "/api/teaching/units?limit=25&offset=0"
  );

  return {
    units
  };
};
