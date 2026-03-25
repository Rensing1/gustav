import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { BreadcrumbItem } from "$lib/types/navigation";

type TeachingCourseListItem = {
  id: string;
  title: string;
};

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const courses = await requireBackendJson<TeachingCourseListItem[]>(
    fetch,
    cookies,
    "/api/teaching/courses?limit=25&offset=0"
  );

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Kurse"
    }
  ];

  return {
    breadcrumbs,
    courses,
    pageCopy:
      "Die Kursliste bleibt bewusst scanbar und ruhig, damit Mitglieder, Einheiten und Diagnostik schnell erreichbar sind.",
    pageTitle: "Kurse"
  };
};
