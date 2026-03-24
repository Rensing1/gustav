import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { DiagnosticsLearnerProfileView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "diagnostics");

  const profile = await requireBackendJson<DiagnosticsLearnerProfileView>(
    fetch,
    cookies,
    `/api/diagnostics/views/learners/${params.studentSub}/profile`
  );

  return {
    profile
  };
};
