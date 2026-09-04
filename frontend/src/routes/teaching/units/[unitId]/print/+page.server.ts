import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherUnitPrintableContent } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");
  const printable = await requireBackendJson<TeacherUnitPrintableContent>(
    fetch,
    cookies,
    `/api/teaching/units/${params.unitId}/printable-content`,
    { authRedirectPath }
  );

  return {
    breadcrumbs: [] as BreadcrumbItem[],
    hidePageHeading: true,
    pageCopy: "Wähle Materialien und Aufgaben für eine Schülerfassung aus.",
    pageTitle: "Druckfassung erstellen",
    printable
  };
};
