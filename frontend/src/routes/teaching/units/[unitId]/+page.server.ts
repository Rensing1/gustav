import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { BreadcrumbItem } from "$lib/types/navigation";

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

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Lerneinheiten",
      href: "/teaching/units"
    },
    {
      label: unit.title
    }
  ];

  return {
    breadcrumbs,
    pageCopy: "Typ, Zusammenfassung und Abschnittsstruktur bleiben als ruhige Detailfläche lesbar.",
    pageTitle: unit.title,
    sections,
    unit,
  };
};
