import type { PageServerLoad } from "./$types";

import { readJsonOrNull } from "$lib/server/api";

type TeachingUnitListItem = {
  id: string;
  title: string;
  summary?: string | null;
  unit_type?: string | null;
};

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const units = (await readJsonOrNull(fetch, cookies, "/api/teaching/units?limit=25&offset=0")) as
    | TeachingUnitListItem[]
    | null;

  return {
    units: units ?? []
  };
};
