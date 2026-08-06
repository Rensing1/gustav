import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const home = await requireBackendJson<TeacherHome>(
    fetch,
    cookies,
    "/api/teaching/views/teacher-home",
    { authRedirectPath }
  );

  return {
    home,
    hidePageHeading: true,
    wideWorkspaceShell: true,
    pageTitle: "Weiterarbeiten"
  };
};
