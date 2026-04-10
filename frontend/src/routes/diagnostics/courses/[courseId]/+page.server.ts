import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { DiagnosticsCourseMatrixView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "diagnostics");

  const matrix = await requireBackendJson<DiagnosticsCourseMatrixView>(
    fetch,
    cookies,
    `/api/diagnostics/views/courses/${params.courseId}/matrix`
  );

  return {
    matrix
  };
};
