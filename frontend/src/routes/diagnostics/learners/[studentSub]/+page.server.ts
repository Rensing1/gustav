import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { DiagnosticsLearnerProfileView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  await requireParentSpaceBootstrap(parent, currentPath(url), "diagnostics");

  const profile = await requireBackendJson<DiagnosticsLearnerProfileView>(
    fetch,
    cookies,
    `/api/diagnostics/views/learners/${params.studentSub}/profile`
  );

  return {
    profile
  };
};
