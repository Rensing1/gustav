import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { BreadcrumbItem } from "$lib/types/navigation";

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

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Lerneinheiten"
    }
  ];

  return {
    breadcrumbs,
    pageCopy:
      "Die Objektliste für Lerneinheiten bleibt scanbar und führt in ruhige Detailansichten statt in die alte SSR-Strecke.",
    pageTitle: "Lerneinheiten",
    units
  };
};
