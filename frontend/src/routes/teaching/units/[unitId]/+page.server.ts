import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";

type TeachingUnitDetail = {
  id: string;
  title: string;
  summary?: string | null;
  unit_type?: string | null;
};

type TeachingSectionListItem = {
  id: string;
  title: string;
  position?: number | null;
};

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const unit = await requireBackendJson<TeachingUnitDetail>(
    fetch,
    cookies,
    `/api/teaching/units/${params.unitId}`
  );
  const sections = await requireBackendJson<TeachingSectionListItem[]>(
    fetch,
    cookies,
    `/api/teaching/units/${params.unitId}/sections`
  );

  return {
    unit,
    sections
  };
};
