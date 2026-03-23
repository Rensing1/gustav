import type { PageServerLoad } from "./$types";

import { readJsonOrNull } from "$lib/server/api";

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

export const load: PageServerLoad = async ({ fetch, cookies, params }) => {
  const unit = (await readJsonOrNull(fetch, cookies, `/api/teaching/units/${params.unitId}`)) as
    | TeachingUnitDetail
    | null;
  const sections = (await readJsonOrNull(fetch, cookies, `/api/teaching/units/${params.unitId}/sections`)) as
    | TeachingSectionListItem[]
    | null;

  return {
    unit,
    sections: sections ?? []
  };
};
