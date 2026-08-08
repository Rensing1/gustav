import type { PageServerLoad } from "./$types";

import { BackendRequestError, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseContextView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";
import { buildUsageApiSearch } from "./usage-search";
import {
  courseUsageForBrowser,
  type TeacherCourseAiUsageApiView,
  usageLoadErrorMessage
} from "./usage-view";
import { error } from "@sveltejs/kit";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const apiSearch = buildUsageApiSearch(url.searchParams);
  // Totals remain course-wide while the API returns the smallest valid learner page.
  apiSearch.set("limit", "1");
  const query = apiSearch.toString();
  const usagePath = `/api/teaching/views/courses/${params.courseId}/ai-usage${query ? `?${query}` : ""}`;

  let usage: TeacherCourseAiUsageApiView;
  let context: TeacherCourseContextView;
  try {
    [usage, context] = await Promise.all([
      requireBackendJson<TeacherCourseAiUsageApiView>(fetch, cookies, usagePath, { authRedirectPath }),
      requireBackendJson<TeacherCourseContextView>(
        fetch,
        cookies,
        `/api/teaching/views/courses/${params.courseId}/context?limit=1&offset=0`,
        { authRedirectPath }
      )
    ]);
  } catch (caught) {
    if (caught instanceof BackendRequestError) {
      throw error(caught.response.status, usageLoadErrorMessage(caught.response.status));
    }
    throw caught;
  }

  return {
    breadcrumbs: [] as BreadcrumbItem[],
    filterValues: {
      fromDate: url.searchParams.get("from_date") ?? "",
      toDate: url.searchParams.get("to_date") ?? "",
      unitId: url.searchParams.get("unit_id") ?? ""
    },
    hidePageHeading: true,
    pageCopy: "Technischer Verbrauch nach Modell und Nutzungsart",
    pageTitle: "KI-Nutzung",
    units: context.units.map((unit) => ({ id: unit.id, title: unit.title })),
    usage: courseUsageForBrowser(usage),
    wideWorkspaceShell: true
  };
};
