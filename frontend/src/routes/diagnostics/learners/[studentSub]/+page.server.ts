import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { DiagnosticsLearnerProfileView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params }) => {
  const profile = await readTypedJsonOrNull<DiagnosticsLearnerProfileView>(
    fetch,
    cookies,
    `/api/diagnostics/views/learners/${params.studentSub}/profile`
  );

  return {
    profile
  };
};
