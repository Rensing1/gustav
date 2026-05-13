import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearnerHome } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");

  const home = await requireBackendJson<LearnerHome>(
    fetch,
    cookies,
    "/api/learning/views/learner-home",
    { authRedirectPath }
  );

  const breadcrumbs: BreadcrumbItem[] = [{ label: "Lernraum" }];

  return {
    breadcrumbs,
    hidePageHeading: true,
    pageTitle: "Meine Klassen",
    home
  };
};
