import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { DiagnosticsCourseMatrixView } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies, params }) => {
  const matrix = await readTypedJsonOrNull<DiagnosticsCourseMatrixView>(
    fetch,
    cookies,
    `/api/diagnostics/views/courses/${params.courseId}/matrix`
  );

  return {
    matrix
  };
};
